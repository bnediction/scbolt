"""Concurrent domain-portfolio execution for BoNesis selection."""

from __future__ import annotations

import os
import sys
import time
from collections import OrderedDict
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import ExitStack
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Lock
from typing import Any, NoReturn

import bonesis

from scbolt import console
from scbolt.runtime import (
    SolverCapacityError,
    SolverDeadline,
    SolverPatience,
    SolverPatienceExpired,
    SolverTimeout,
    close_solver_progress,
    current_rss_bytes,
    format_memory_size,
    interrupt_solver_view,
    iter_solver_view,
    release_unused_memory,
)

from ._continuation import (
    DomainCandidate,
    DomainCandidateResult,
    DomainMemoryEstimator,
    DomainPhase,
    DomainPortfolioLaunchState,
    DomainWaveLeader,
    bounded_midpoint,
    build_candidate_wave,
    candidate_fits_memory_budget,
    domain_frontier_grace_seconds,
    domain_expansion_gains,
    expansion_domain_size,
    initial_domain_size,
    minimum_domain_gain,
    outcome_counts,
    portfolio_objective_ceiling,
    reduced_domain_expansion_size,
    select_best_candidate,
    solution_objective,
    solution_reaches_domain_ceiling,
    solver_result_certifies_optimum,
    stalled_domain_solver_settings,
    terminal_refinement_solver_settings,
)
from ._selection import (
    TQDM_TO_TTY,
    filter_nodes_objective,
    fork_bonesis,
    get_filter_clingo_settings,
    make_filter_nodes_score_formatter,
    ptqdm,
)
from ._witness import structural_witness

DOMAIN_MEMORY_PROBE_SECONDS = 2.0
DOMAIN_MEMORY_LAUNCH_INTERVAL_SECONDS = 2.0
DOMAIN_MEMORY_COST_FACTOR = 1.10


@dataclass
class DomainWaveMemoryUsage:
    """Track the process-wide RSS peak observed during one domain wave."""

    peak_rss: int | None = None

    def observe(self, rss: int | None) -> None:
        if rss is not None:
            self.peak_rss = max(self.peak_rss or 0, rss)


class CandidateProgressProxy:
    """Forward worker progress events without writing to the terminal."""

    def __init__(self, events: Queue, candidate_index: int) -> None:
        self.events = events
        self.candidate_index = candidate_index

    def set_postfix(self, values=None, refresh=True, **kwargs) -> None:
        self.events.put(("postfix", self.candidate_index, values or kwargs))

    def set_description_str(self, description, refresh=True) -> None:
        # Keep the coordinator's candidate identity visible on every line.
        return None

    def update(self, value=1) -> None:
        self.events.put(("update", self.candidate_index, value))

    def refresh(self) -> None:
        self.events.put(("refresh", self.candidate_index))

    def clear(self) -> None:
        # The parent coordinator clears the complete multi-bar display.
        return None

    def close(self) -> None:
        # Worker completion is tracked by its future, not by the proxy bar.
        return None


class ActiveCandidateViews:
    """Track active views so the coordinator can interrupt a complete wave."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._views = {}
        self._interrupted_candidates = set()
        self._interrupted = False

    def register(self, candidate_index: int, view: Any) -> bool:
        with self._lock:
            if self._interrupted:
                return False
            self._views[candidate_index] = view
        return True

    def unregister(self, candidate_index: int) -> None:
        with self._lock:
            self._views.pop(candidate_index, None)

    def interrupt_one(self, candidate_index: int) -> bool:
        with self._lock:
            view = self._views.get(candidate_index)
            if view is None:
                return False
            self._interrupted_candidates.add(candidate_index)
        # Control.interrupt() is asynchronous-safe. Cancelling the solve
        # handle as well from this coordinator thread races with Clingo's
        # worker and can corrupt its native state.
        interrupt_solver_view(view, cancel_handler=False)
        return True

    def interrupt_all(self) -> None:
        with self._lock:
            self._interrupted = True
            self._interrupted_candidates.update(self._views)
            views = tuple(self._views.values())
        for view in views:
            interrupt_solver_view(view, cancel_handler=False)

    def candidate_interrupted(self, candidate_index: int) -> bool:
        with self._lock:
            return candidate_index in self._interrupted_candidates

    def active_candidates(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(self._views)


def solve_domain_candidate(
    bo: bonesis.BoNesis,
    candidate: DomainCandidate,
    *,
    max_clause: int,
    witness: Iterable[str],
    clingo_mode: str,
    clingo_strategy: str,
    clingo_configuration: str | None,
    events: Queue,
    active_views: ActiveCandidateViews,
    cancelled: Event,
) -> DomainCandidateResult:
    """Solve one candidate domain and report events to the coordinator."""

    witness = tuple(witness)
    best_model = [None]

    def intermediate_solution(model) -> None:
        best_model[0] = model
        nodes, structural_model = model
        events.put(
            (
                "model",
                candidate.index,
                tuple(sorted(nodes)),
                tuple(structural_model),
            )
        )

    def progress(*_args, **_kwargs):
        return CandidateProgressProxy(events, candidate.index)

    stage_bo = fork_bonesis(
        bo,
        max_clause=max_clause,
        domain_nodes=candidate.nodes,
        witness=witness,
    )
    extra_clingo_options = list(candidate.solver_options)
    if witness:
        extra_clingo_options.insert(0, "--heuristic=Domain")
    view_settings = get_filter_clingo_settings(
        clingo_mode,
        clingo_strategy,
        clingo_configuration,
        *extra_clingo_options,
    )
    view_settings["parallel"] = 1
    view = bonesis.NodesView(
        stage_bo,
        mode=clingo_mode,
        extra=structural_witness,
        intermediate_model_cb=intermediate_solution,
        clingo_opt_strategy=clingo_strategy,
        progress=progress,
        **view_settings,
    )
    try:
        iterator = iter_solver_view(view)
    except SolverCapacityError:
        close_solver_progress(view)
        return DomainCandidateResult(
            candidate,
            "unknown",
            unknown_reason="capacity",
        )
    if not active_views.register(candidate.index, view):
        interrupt_solver_view(view, cancel_handler=False)
        close_solver_progress(view)
        return DomainCandidateResult(candidate, "cancelled")
    events.put(("ready", candidate.index, current_rss_bytes()))

    outcome = "sat"
    optimum_certified = False
    solution = ()
    structural_model = ()
    try:
        solution, structural_model = next(iterator)
        # In opt mode BoNesis can return the last witness after Control.interrupt().
        # Only natural solver exhaustion certifies that witness as optimal.
        optimum_certified = solver_result_certifies_optimum(
            clingo_mode,
            interrupted=(
                cancelled.is_set()
                or active_views.candidate_interrupted(candidate.index)
                or getattr(view, "interrupted", False)
            ),
        )
    except StopIteration:
        outcome = (
            "cancelled"
            if cancelled.is_set() or active_views.candidate_interrupted(candidate.index)
            else "unsat"
        )
    except RuntimeError:
        if not cancelled.is_set() and not active_views.candidate_interrupted(
            candidate.index
        ):
            raise
        outcome = "cancelled"
        if best_model[0] is not None:
            solution, structural_model = best_model[0]
    finally:
        active_views.unregister(candidate.index)
        close_solver_progress(view)

    return DomainCandidateResult(
        candidate=candidate,
        outcome=outcome,
        solution=tuple(sorted(solution)),
        witness=tuple(structural_model),
        optimum_certified=optimum_certified,
    )


def run_domain_wave(
    bo: bonesis.BoNesis,
    candidates: Sequence[DomainCandidate],
    *,
    phase: DomainPhase,
    wave: int,
    max_clause: int,
    witness: Iterable[str],
    incumbent_solution: Iterable[str],
    clingo_mode: str,
    clingo_strategy: str,
    clingo_configuration: str | None,
    patience_seconds: float,
    clause_patience: SolverPatience,
    deadline: SolverDeadline,
    important_nodes: set[str],
    memory_limit: int | None,
    on_model: Callable[[frozenset[str], Sequence[str], Sequence[str]], bool],
    memory_estimator: DomainMemoryEstimator | None = None,
) -> tuple[DomainCandidateResult, ...]:
    """Evaluate one domain wave and release its solver memory afterward."""

    memory_usage = DomainWaveMemoryUsage()
    try:
        return _run_domain_wave(
            bo,
            candidates,
            phase=phase,
            wave=wave,
            max_clause=max_clause,
            witness=witness,
            incumbent_solution=incumbent_solution,
            clingo_mode=clingo_mode,
            clingo_strategy=clingo_strategy,
            clingo_configuration=clingo_configuration,
            patience_seconds=patience_seconds,
            clause_patience=clause_patience,
            deadline=deadline,
            important_nodes=important_nodes,
            memory_limit=memory_limit,
            on_model=on_model,
            memory_estimator=memory_estimator,
            memory_usage=memory_usage,
        )
    finally:
        memory_before_release = current_rss_bytes()
        memory_usage.observe(memory_before_release)
        release_unused_memory()
        memory_after_release = current_rss_bytes()
        if memory_usage.peak_rss is not None and memory_after_release is not None:
            peak = format_memory_size(memory_usage.peak_rss)
            if memory_limit is not None:
                peak = f"{peak}/{format_memory_size(memory_limit)}"
            released = max(0, memory_usage.peak_rss - memory_after_release)
            console.print_debug(
                "domain wave memory "
                f"(peak={peak}, released={format_memory_size(released)}, "
                f"remaining={format_memory_size(memory_after_release)})",
                flush=True,
            )


def _run_domain_wave(
    bo: bonesis.BoNesis,
    candidates: Sequence[DomainCandidate],
    *,
    phase: DomainPhase,
    wave: int,
    max_clause: int,
    witness: Iterable[str],
    incumbent_solution: Iterable[str],
    clingo_mode: str,
    clingo_strategy: str,
    clingo_configuration: str | None,
    patience_seconds: float,
    clause_patience: SolverPatience,
    deadline: SolverDeadline,
    important_nodes: set[str],
    memory_limit: int | None,
    on_model: Callable[[frozenset[str], Sequence[str], Sequence[str]], bool],
    memory_estimator: DomainMemoryEstimator | None,
    memory_usage: DomainWaveMemoryUsage,
) -> tuple[DomainCandidateResult, ...]:
    """Evaluate one domain wave while rendering all progress in the parent."""

    if not candidates:
        return ()

    progress_stream_context = ExitStack()
    progress_stream = sys.stdout
    close_progress_stream = False
    if TQDM_TO_TTY:
        try:
            progress_stream = progress_stream_context.enter_context(
                console.open_terminal_stream()
            )
            close_progress_stream = True
        except OSError:
            pass

    progress_cursor_saved = False
    progress_options = {}
    if progress_stream.isatty():
        try:
            terminal_rows = os.get_terminal_size(progress_stream.fileno()).lines
        except OSError:
            terminal_rows = len(candidates) + 2
        progress_rows = min(len(candidates) + 1, max(1, terminal_rows - 1))
        progress_options["nrows"] = progress_rows

        # Reserve the complete display before tqdm writes into it. This keeps
        # progress lines out of the terminal scrollback and gives cleanup a
        # stable cursor anchor even when many candidates run concurrently.
        if progress_rows > 1:
            progress_stream.write("\n" * (progress_rows - 1))
            progress_stream.write(f"\033[{progress_rows - 1}A")
        progress_stream.write("\r\033[s")
        progress_stream.flush()
        progress_cursor_saved = True

    events = Queue()
    active_views = ActiveCandidateViews()
    cancelled = Event()
    incumbent_objective = solution_objective(
        incumbent_solution,
        important_nodes,
    )
    score_formatters = {
        candidate.index: make_filter_nodes_score_formatter(
            important_total=len(important_nodes & set(candidate.nodes)),
            node_total=len(candidate.nodes),
        )
        for candidate in candidates
    }
    displayed_objectives = {
        candidate.index: incumbent_objective for candidate in candidates
    }
    candidate_states = {candidate.index: "queued" for candidate in candidates}

    def format_candidate_objective(candidate_index: int) -> Mapping[str, str]:
        """Format the best inherited or locally observed candidate score."""

        important, total = displayed_objectives[candidate_index]
        score = (important, total) if important_nodes else (total,)
        return score_formatters[candidate_index](score)

    def format_candidate_postfix(candidate_index: int) -> Mapping[str, str]:
        """Format candidate state and objective for one domain bar."""

        fields = OrderedDict(format_candidate_objective(candidate_index))
        fields["state"] = candidate_states[candidate_index]
        return fields

    candidate_width = len(str(len(candidates)))
    progress_label = f"Domain {phase}"
    progress_header = ptqdm(
        total=0,
        desc=f"{progress_label} [max clauses={max_clause}, wave={wave}]",
        position=0,
        file=progress_stream,
        bar_format="{desc}",
        **progress_options,
    )
    bars = {
        candidate.index: ptqdm(
            total=float("inf"),
            desc=(
                f"{progress_label} "
                f"[candidate={candidate.index:>{candidate_width}}/"
                f"{len(candidates)}]"
            ),
            postfix={},
            position=position,
            file=progress_stream,
            bar_format="{desc}: {n_fmt:>4}it ({elapsed}{postfix})",
            **progress_options,
        )
        for position, candidate in enumerate(candidates, start=1)
    }
    for candidate in candidates:
        bars[candidate.index].set_postfix(
            format_candidate_postfix(candidate.index),
            refresh=True,
        )
    progress_display_closed = False

    def close_progress_display() -> None:
        """Clear the complete multi-bar display exactly once."""

        nonlocal progress_display_closed
        if progress_display_closed:
            return
        progress_display_closed = True

        for bar in reversed(tuple(bars.values())):
            bar.close()
        progress_header.close()

        if progress_cursor_saved:
            # Restore the stable anchor saved before tqdm allocated its bars,
            # then erase the complete transient display in one operation.
            progress_stream.write("\033[u\r\033[J")
            progress_stream.flush()

    candidate_by_index = {candidate.index: candidate for candidate in candidates}
    wave_objective_ceiling = portfolio_objective_ceiling(
        candidates,
        important_nodes,
    )
    observed_models = {}
    wave_patience = SolverPatience(
        patience_seconds,
        start_immediately=False,
    )
    frontier_grace_seconds = domain_frontier_grace_seconds(patience_seconds)
    wave_patience_started = False
    wave_leader = DomainWaveLeader(objective=incumbent_objective)
    stop_reason = None
    memory_interrupted = set()
    executor = ThreadPoolExecutor(
        max_workers=len(candidates),
        thread_name_prefix="scbolt-domain",
    )
    candidate_queue = list(candidates)
    futures = {}
    pending = set()
    memory_baseline = current_rss_bytes() if memory_limit is not None else None
    memory_usage.observe(memory_baseline)
    candidate_domain_size = len(candidates[0].nodes)
    estimated_candidate_cost = (
        memory_estimator.estimate(
            domain_size=candidate_domain_size,
            max_clause=max_clause,
        )
        if memory_estimator is not None
        else None
    )
    maximum_candidate_cost = estimated_candidate_cost or 0.0
    launch_state = DomainPortfolioLaunchState(
        probe_required=(memory_limit is not None and estimated_candidate_cost is None),
        probe_seconds=DOMAIN_MEMORY_PROBE_SECONDS,
        launch_interval_seconds=(
            DOMAIN_MEMORY_LAUNCH_INTERVAL_SECONDS if memory_limit is not None else 0.0
        ),
    )
    grounding_candidates = set()
    maximum_concurrent_candidates = 0

    def set_candidate_state(
        candidate_index: int,
        state: str,
        *,
        refresh: bool = False,
    ) -> None:
        """Update one candidate bar state while preserving its score."""

        if candidate_states.get(candidate_index) == state:
            return
        candidate_states[candidate_index] = state
        bars[candidate_index].set_postfix(
            format_candidate_postfix(candidate_index),
            refresh=refresh,
        )

    def submit_candidate(candidate: DomainCandidate) -> None:
        nonlocal maximum_concurrent_candidates

        future = executor.submit(
            solve_domain_candidate,
            bo,
            candidate,
            max_clause=max_clause,
            witness=witness,
            clingo_mode=clingo_mode,
            clingo_strategy=clingo_strategy,
            clingo_configuration=clingo_configuration,
            events=events,
            active_views=active_views,
            cancelled=cancelled,
        )
        futures[future] = candidate
        pending.add(future)
        maximum_concurrent_candidates = max(
            maximum_concurrent_candidates,
            len(pending),
        )
        if memory_limit is not None:
            grounding_candidates.add(candidate.index)
        set_candidate_state(candidate.index, "grounding", refresh=True)
        launch_state.mark_submitted(time.monotonic())

    def observe_memory(
        rss_sample: int | None = None,
    ) -> tuple[int | None, float | None]:
        nonlocal maximum_candidate_cost

        rss = current_rss_bytes() if rss_sample is None else rss_sample
        memory_usage.observe(rss)
        if rss is None or memory_limit is None or memory_baseline is None:
            return rss, None
        if maximum_concurrent_candidates:
            # Solver allocations can remain resident after a worker finishes.
            # Keep the denominator at the wave's concurrency high-water mark
            # instead of attributing retained memory to the last pending worker.
            candidate_cost = (
                max(0, rss - memory_baseline) / maximum_concurrent_candidates
            )
            maximum_candidate_cost = max(
                maximum_candidate_cost,
                candidate_cost,
            )
            if memory_estimator is not None:
                memory_estimator.observe(
                    candidate_cost,
                    domain_size=candidate_domain_size,
                    max_clause=max_clause,
                )
        return rss, maximum_candidate_cost

    def can_launch_candidate() -> bool:
        if not candidate_queue:
            return False
        now = time.monotonic()
        if not launch_state.ready_for_launch(
            now,
            has_pending=bool(pending),
        ):
            return False
        if not launch_state.probe_complete:
            return True
        if any(futures[future].index in memory_interrupted for future in pending):
            return False
        rss, candidate_cost = observe_memory()
        return candidate_fits_memory_budget(
            memory_limit,
            rss,
            candidate_cost,
            cost_factor=DOMAIN_MEMORY_COST_FACTOR,
            reserved_candidates=len(grounding_candidates),
        )

    def launch_candidate() -> bool:
        if not can_launch_candidate():
            return False
        submit_candidate(candidate_queue.pop(0))
        return True

    def least_advanced_active_candidate() -> int | None:
        active_candidates = {
            candidate_index
            for candidate_index in active_views.active_candidates()
            if candidate_index not in memory_interrupted
        }
        if len(active_candidates) <= 1:
            return None

        def candidate_key(candidate_index: int) -> tuple[int, int, int, int]:
            has_model = int(candidate_index in observed_models)
            important, total = displayed_objectives[candidate_index]
            return has_model, important, total, -candidate_index

        return min(active_candidates, key=candidate_key)

    def print_wave_warning(message: str) -> None:
        """Write a warning without corrupting the active multi-bar display."""

        line = console.format_message("WARNING", message)
        with ptqdm.external_write_mode(file=progress_stream):
            print(line, file=progress_stream, flush=True)

        if close_progress_stream and os.getenv("SCBOLT_LOGGING_TO_FILE") == "true":
            logfile = os.getenv("LOGFILE")
            if logfile:
                try:
                    with open(logfile, "a", encoding="utf-8") as stream:
                        print(line, file=stream, flush=True)
                except OSError:
                    pass

    def enforce_memory_limit() -> None:
        if memory_limit is None:
            return
        rss, _ = observe_memory()
        if rss is None or rss <= memory_limit:
            return
        if any(futures[future].index in memory_interrupted for future in pending):
            return
        candidate_index = least_advanced_active_candidate()
        if candidate_index is None:
            return
        if active_views.interrupt_one(candidate_index):
            active_count = len(active_views.active_candidates())
            memory_interrupted.add(candidate_index)
            set_candidate_state(candidate_index, "stopping", refresh=True)
            print_wave_warning(
                "memory limit reached; reducing domain portfolio "
                f"(active={active_count} -> {active_count - 1}, "
                f"rss={format_memory_size(rss)}, "
                f"limit={format_memory_size(memory_limit)})"
            )

    def process_event(event) -> None:
        nonlocal stop_reason, wave_patience_started

        kind, candidate_index, *payload = event
        if kind == "ready":
            grounding_candidates.discard(candidate_index)
            set_candidate_state(candidate_index, "solving", refresh=True)
            if not wave_patience_started:
                wave_patience.start()
                wave_patience_started = True
            else:
                wave_patience.ensure_remaining(frontier_grace_seconds)
            launch_state.mark_probe_candidate_ready(time.monotonic())
            observe_memory(payload[0])
            return

        bar = bars[candidate_index]
        if kind == "postfix":
            values = payload[0]
            if "score" in values:
                objective = filter_nodes_objective(
                    values["score"],
                    has_important_nodes=bool(important_nodes),
                )
                displayed_objectives[candidate_index] = max(
                    objective,
                    displayed_objectives[candidate_index],
                )
                values = format_candidate_postfix(candidate_index)
            else:
                values = {
                    **format_candidate_postfix(candidate_index),
                    **values,
                }
            bar.set_postfix(values, refresh=False)
        elif kind == "update":
            bar.update(payload[0])
        elif kind == "refresh":
            bar.refresh()
        elif kind == "model":
            solution, structural_model = payload
            candidate = candidate_by_index[candidate_index]
            objective = solution_objective(solution, important_nodes)
            candidate_optimal = solution_reaches_domain_ceiling(
                solution,
                candidate.nodes,
                important_nodes,
            )
            observed_models[candidate_index] = DomainCandidateResult(
                candidate=candidate,
                outcome="sat",
                solution=solution,
                witness=structural_model,
                optimum_certified=candidate_optimal,
            )
            leader_update = wave_leader.update(
                candidate_index,
                solution,
                important_nodes,
            )
            if leader_update == "improved":
                wave_patience.reset()
            elif leader_update == "joined":
                wave_patience.ensure_remaining(frontier_grace_seconds)
            if on_model(
                candidate.nodes,
                solution,
                structural_model,
            ):
                clause_patience.reset()
            if objective == wave_objective_ceiling and stop_reason is None:
                stop_reason = "portfolio-optimal"

    progress_input_guard = console.guard_progress_input(progress_stream)
    try:
        progress_input_guard.__enter__()
        submit_candidate(candidate_queue.pop(0))
        while pending or candidate_queue:
            if stop_reason is None:
                if not launch_state.probe_complete:
                    observe_memory()
                    launch_state.update_probe(
                        time.monotonic(),
                        has_pending=bool(pending),
                    )
                if launch_state.probe_complete:
                    observe_memory()
                while launch_candidate():
                    pass
            try:
                event = events.get(timeout=0.05)
            except Empty:
                event = None
            if event is not None:
                process_event(event)
                while True:
                    try:
                        process_event(events.get_nowait())
                    except Empty:
                        break

            if stop_reason is None:
                remaining = deadline.remaining()
                if remaining is not None and remaining <= 0:
                    stop_reason = "timeout"
                else:
                    patience_remaining = clause_patience.remaining()
                    if patience_remaining is not None and patience_remaining <= 0:
                        stop_reason = "clause-patience"
                    else:
                        patience_remaining = wave_patience.remaining()
                        if patience_remaining is not None and patience_remaining <= 0:
                            stop_reason = "domain-patience"

            if stop_reason is None:
                enforce_memory_limit()
            if stop_reason is not None:
                cancelled.set()
                active_views.interrupt_all()

            done, current_pending = wait(
                pending,
                timeout=0,
                return_when=FIRST_COMPLETED,
            )
            for future in done:
                candidate_index = futures[future].index
                grounding_candidates.discard(candidate_index)
                set_candidate_state(candidate_index, "done")
            pending = set(current_pending)
            if phase in {"completion", "refinement"} and stop_reason is None:
                for future in done:
                    if future.result().optimum_certified:
                        stop_reason = "portfolio-optimal"
                        cancelled.set()
                        active_views.interrupt_all()
                        break
            if stop_reason is not None and not pending:
                break

        while True:
            try:
                process_event(events.get_nowait())
            except Empty:
                break

        results = []
        for future, candidate in futures.items():
            result = future.result()
            observed_result = observed_models.get(candidate.index)
            if observed_result is not None and (
                result.outcome == "cancelled"
                or (observed_result.optimum_certified and not result.optimum_certified)
            ):
                result = observed_result
            elif result.outcome == "cancelled" and (
                candidate.index in memory_interrupted
                or stop_reason == "domain-patience"
            ):
                result = DomainCandidateResult(candidate, "unknown")
            results.append(result)
        if candidate_queue:
            queued_outcome = (
                "unknown" if stop_reason == "domain-patience" else "cancelled"
            )
            results.extend(
                DomainCandidateResult(candidate, queued_outcome)
                for candidate in candidate_queue
            )
    finally:
        try:
            close_progress_display()
        finally:
            try:
                cancelled.set()
                active_views.interrupt_all()
                executor.shutdown(wait=True, cancel_futures=True)
            finally:
                progress_input_guard.__exit__(*sys.exc_info())
                progress_stream_context.close()

    if stop_reason == "timeout":
        raise SolverTimeout
    if stop_reason == "clause-patience":
        raise SolverPatienceExpired

    return tuple(results)


@dataclass(frozen=True)
class DomainContinuationState:
    """Best domain and witness retained after one clause-bound search."""

    domain: frozenset[str]
    solution: tuple[str, ...]
    witness: tuple[str, ...]
    complete_domain_unsat: bool = False
    complete_domain_optimal: bool = False
    terminal_refinement_used: bool = False
    continuation_exhausted: bool = False
    bb_lin_fallback_used: bool = False


def print_domain_wave_summary(
    *,
    phase: str,
    max_clause: int,
    wave: int,
    results: Sequence[DomainCandidateResult],
    selected: DomainCandidateResult | None,
) -> None:
    """Persist one compact summary after clearing dynamic candidate bars."""

    counts = outcome_counts(results)
    context = [
        f"wave={wave}",
        f"phase={phase}",
        f"max clauses={max_clause}",
    ]
    certified_count = sum(
        result.outcome == "sat" and result.optimum_certified for result in results
    )
    outcomes = [
        f"certified={certified_count}",
        f"sat={counts['sat'] - certified_count}",
        f"unsat={counts['unsat']}",
    ]
    if counts["unknown"]:
        outcomes.append(f"unknown={counts['unknown']}")
    if counts["cancelled"]:
        outcomes.append(f"cancelled={counts['cancelled']}")
    if selected is not None:
        result = f"solution={len(selected.solution)}/{len(selected.candidate.nodes)}"
    else:
        result = "no solution"
    console.print_info(
        f"domain continuation [{', '.join(context)}]: {result} ({', '.join(outcomes)})",
        flush=True,
    )
    capacity_count = sum(
        candidate.unknown_reason == "capacity" for candidate in results
    )
    if capacity_count:
        console.print_warning(
            "solver grounding capacity reached in domain portfolio "
            f"[{', '.join(context)}]: "
            f"affected={capacity_count}/{len(results)}, outcome=UNKNOWN",
            flush=True,
        )


def _raise_unresolved_complete_domain(
    results: Sequence[DomainCandidateResult],
    *,
    phase: str,
) -> NoReturn:
    """Classify a complete-domain portfolio that returned no witness."""

    capacity_count = sum(result.unknown_reason == "capacity" for result in results)
    if capacity_count:
        raise SolverCapacityError(
            "ASP grounding exceeded Clasp's internal program-node limit "
            f"in {capacity_count}/{len(results)} complete-domain "
            f"{phase} workers"
        )
    raise RuntimeError(f"complete-domain {phase} portfolio ended without a result")


@dataclass(frozen=True)
class _EvaluatedDomainWave:
    """Candidates and classified results produced by one domain wave."""

    candidates: tuple[DomainCandidate, ...]
    results: tuple[DomainCandidateResult, ...]
    selected: DomainCandidateResult | None
    counts: Mapping[str, int]


class DomainContinuationRunner:
    """Run acquisition and expansion at one Boolean clause bound."""

    def __init__(
        self,
        bo: bonesis.BoNesis,
        *,
        max_clause: int,
        initial_domain: Iterable[str],
        initial_solution: Iterable[str],
        initial_witness: Iterable[str],
        expansion_only: bool,
        required_nodes: set[str],
        important_nodes: set[str],
        jobs: int,
        seed: int,
        clingo_mode: str,
        clingo_strategy: str,
        clingo_configuration: str | None,
        domain_patience_seconds: float,
        minimum_domain_yield: float,
        max_domain_refreshes: int,
        clause_patience: SolverPatience,
        deadline: SolverDeadline,
        memory_limit: int | None,
        on_model: Callable[
            [frozenset[str], Sequence[str], Sequence[str]],
            bool,
        ],
        on_selected: Callable[
            [frozenset[str], Sequence[str], Sequence[str]],
            None,
        ],
        memory_estimator: DomainMemoryEstimator | None = None,
    ) -> None:
        self.bo = bo
        self.max_clause = max_clause
        self.expansion_only = expansion_only
        self.required_nodes = required_nodes
        self.important_nodes = important_nodes
        self.jobs = jobs
        self.seed = seed
        self.clingo_configuration = clingo_configuration
        self.domain_patience_seconds = domain_patience_seconds
        self.minimum_domain_yield = minimum_domain_yield
        self.max_domain_refreshes = max_domain_refreshes
        self.clause_patience = clause_patience
        self.deadline = deadline
        self.memory_limit = memory_limit
        self.on_model = on_model
        self.on_selected = on_selected
        self.memory_estimator = memory_estimator

        self.complete_domain = frozenset(bo.domain.nodes)
        self.current_domain = frozenset(initial_domain)
        self.current_solution = tuple(sorted(initial_solution))
        self.current_witness = tuple(initial_witness)
        self.wave_clingo_mode = clingo_mode
        self.wave_clingo_strategy = clingo_strategy
        self.bb_lin_fallback_used = False
        self.minimum_fallback_retry = False
        self.wave = 0

    def run(self) -> DomainContinuationState:
        """Acquire a witness when needed and expand it to the full domain."""

        if not self.current_domain:
            self.current_domain = frozenset(self.required_nodes & self.complete_domain)
        if not self.current_domain <= self.complete_domain:
            raise ValueError("initial continuation domain exceeds the complete domain")
        if self.expansion_only and (
            not self.current_solution or not self.current_witness
        ):
            raise ValueError(
                "expansion-only domain continuation requires an initial "
                "structural witness with selected nodes"
            )

        if not self.current_witness:
            acquisition_state = self._acquire()
            if acquisition_state is not None:
                return acquisition_state

        expansion_state = self._expand()
        if expansion_state is not None:
            return expansion_state
        return self._complete()

    def _acquire(self) -> DomainContinuationState | None:
        """Find an initial satisfiable subdomain and structural witness."""

        minimum_size = len(self.current_domain)
        lower_unsat = minimum_size - 1
        upper_unknown = len(self.complete_domain) + 1
        target_size = initial_domain_size(
            minimum_size,
            len(self.complete_domain),
        )

        while not self.current_witness:
            is_minimum_fallback_wave = self.minimum_fallback_retry
            self.minimum_fallback_retry = False
            evaluation = self._run_new_wave(
                phase="acquisition",
                base_domain=self.current_domain,
                target_size=target_size,
                witness=(),
            )
            if evaluation is None:
                raise RuntimeError("domain acquisition produced no candidates")

            evaluated_domains = {candidate.nodes for candidate in evaluation.candidates}
            evaluation, _, _ = self._refresh_unresolved(
                evaluation,
                base_domain=self.current_domain,
                target_size=target_size,
                witness=(),
                evaluated_domains=evaluated_domains,
                enabled=not is_minimum_fallback_wave,
            )
            selected = evaluation.selected
            counts = evaluation.counts

            if selected is not None:
                self.current_domain = selected.candidate.nodes
                self.current_solution = selected.solution
                self.current_witness = selected.witness
                self.on_selected(
                    self.current_domain,
                    self.current_solution,
                    self.current_witness,
                )
                return None

            if target_size == len(self.complete_domain) and counts["unsat"]:
                return DomainContinuationState(
                    self.current_domain,
                    self.current_solution,
                    self.current_witness,
                    complete_domain_unsat=True,
                )

            if evaluation.results and counts["unsat"] == len(evaluation.results):
                lower_unsat = max(lower_unsat, target_size)
                upper = min(
                    upper_unknown - 1,
                    len(self.complete_domain),
                )
                if lower_unsat < upper:
                    target_size = bounded_midpoint(lower_unsat, upper)
                else:
                    target_size = min(
                        len(self.complete_domain),
                        target_size + 1,
                    )
                continue

            if counts["unknown"] or counts["cancelled"]:
                upper_unknown = min(upper_unknown, target_size)
                lower = max(minimum_size, lower_unsat + 1)
                upper = upper_unknown - 1
                if lower <= upper:
                    next_target_size = bounded_midpoint(lower, upper)
                else:
                    next_target_size = max(
                        minimum_size,
                        min(target_size, upper_unknown),
                    )
                if next_target_size == target_size:
                    if self._switch_to_fallback(
                        reason="minimum acquisition unresolved",
                        domain_size=target_size,
                    ):
                        continue
                    return DomainContinuationState(
                        self.current_domain,
                        self.current_solution,
                        self.current_witness,
                        continuation_exhausted=True,
                        bb_lin_fallback_used=self.bb_lin_fallback_used,
                    )
                target_size = next_target_size
                continue

            raise RuntimeError("domain continuation ended without a solver outcome")

        return None

    def _expand(self) -> DomainContinuationState | None:
        """Expand a retained witness through progressively larger domains."""

        expansion_target = expansion_domain_size(
            len(self.current_domain),
            len(self.complete_domain),
        )
        while expansion_target < len(self.complete_domain):
            is_minimum_fallback_wave = self.minimum_fallback_retry
            self.minimum_fallback_retry = False
            expansion_base_domain = self.current_domain
            expansion_base_solution = self.current_solution
            expansion_size = expansion_target - len(expansion_base_domain)
            required_gain = minimum_domain_gain(
                expansion_size,
                self.minimum_domain_yield,
            )

            evaluation = self._run_new_wave(
                phase="expansion",
                base_domain=expansion_base_domain,
                target_size=expansion_target,
                witness=self.current_witness,
            )
            if evaluation is None:
                raise RuntimeError("domain expansion produced no candidates")
            evaluated_domains = {candidate.nodes for candidate in evaluation.candidates}
            evaluation, refresh_count, refresh_space_exhausted = (
                self._refresh_unresolved(
                    evaluation,
                    base_domain=expansion_base_domain,
                    target_size=expansion_target,
                    witness=self.current_witness,
                    evaluated_domains=evaluated_domains,
                    enabled=not is_minimum_fallback_wave,
                )
            )

            selected = evaluation.selected
            if selected is None:
                reduced_step = reduced_domain_expansion_size(expansion_size)
                if reduced_step is None:
                    if self._switch_to_fallback(
                        reason="minimum expansion unresolved",
                        domain_size=len(expansion_base_domain),
                    ):
                        continue
                    return DomainContinuationState(
                        self.current_domain,
                        self.current_solution,
                        self.current_witness,
                        continuation_exhausted=True,
                        bb_lin_fallback_used=self.bb_lin_fallback_used,
                    )
                expansion_target = len(expansion_base_domain) + reduced_step
                continue

            self._adopt_candidate(selected)
            important_gain, retained_gain = domain_expansion_gains(
                expansion_base_solution,
                self.current_solution,
                self.important_nodes,
            )
            while (
                self.minimum_domain_yield > 0
                and important_gain == 0
                and retained_gain < required_gain
                and refresh_count < self.max_domain_refreshes
            ):
                refresh_core = expansion_base_domain | frozenset(self.current_solution)
                protected_additions = len(refresh_core - expansion_base_domain)

                def announce_refresh(_candidate_count: int) -> None:
                    console.print_debug(
                        "refreshing domain "
                        f"(attempt={refresh_count + 1}/"
                        f"{self.max_domain_refreshes}, "
                        f"size={expansion_target}, "
                        f"yield={retained_gain}/{expansion_size} "
                        f"[{retained_gain / expansion_size:.1%} < "
                        f"{self.minimum_domain_yield:.1%}], "
                        f"protected={protected_additions})",
                        flush=True,
                    )

                refreshed = self._run_new_wave(
                    phase="refresh",
                    base_domain=refresh_core,
                    target_size=expansion_target,
                    witness=self.current_witness,
                    excluded_domains=evaluated_domains,
                    announce=announce_refresh,
                )
                if refreshed is None:
                    refresh_space_exhausted = True
                    break

                refresh_count += 1
                evaluated_domains.update(
                    candidate.nodes for candidate in refreshed.candidates
                )
                if refreshed.selected is not None:
                    self._adopt_candidate(refreshed.selected)
                important_gain, retained_gain = domain_expansion_gains(
                    expansion_base_solution,
                    self.current_solution,
                    self.important_nodes,
                )

            if (
                self.minimum_domain_yield > 0
                and important_gain == 0
                and retained_gain < required_gain
            ):
                gain = (
                    f"{retained_gain}/{expansion_size} "
                    f"({retained_gain / expansion_size:.1%})"
                )
                if refresh_space_exhausted:
                    console.print_warning(
                        "domain refresh space exhausted "
                        f"(gain={gain}, "
                        f"minimum={self.minimum_domain_yield:.1%}, "
                        f"domains tested={len(evaluated_domains)}); "
                        "expanding domain",
                        flush=True,
                    )
                elif refresh_count == self.max_domain_refreshes:
                    console.print_warning(
                        "minimum domain yield not reached before refresh limit "
                        f"(gain={gain}, "
                        f"minimum={self.minimum_domain_yield:.1%}, "
                        f"refreshes={refresh_count}); expanding domain",
                        flush=True,
                    )

            expansion_target = expansion_domain_size(
                len(self.current_domain),
                len(self.complete_domain),
            )

        return None

    def _complete(self) -> DomainContinuationState:
        """Evaluate the complete domain and invoke refinement when required."""

        evaluation = self._run_new_wave(
            phase="completion",
            base_domain=self.current_domain,
            target_size=len(self.complete_domain),
            witness=self.current_witness,
        )
        if evaluation is None:
            raise RuntimeError("domain completion produced no candidates")
        if evaluation.selected is not None:
            self._adopt_candidate(evaluation.selected)

        if evaluation.selected is None and evaluation.counts["unsat"]:
            return DomainContinuationState(
                self.current_domain,
                self.current_solution,
                self.current_witness,
                complete_domain_unsat=True,
            )

        complete_domain_optimal = bool(
            evaluation.selected is not None and evaluation.selected.optimum_certified
        )
        refinement_settings = terminal_refinement_solver_settings(
            self.wave_clingo_mode,
            self.wave_clingo_strategy,
            optimum_certified=complete_domain_optimal,
        )
        if refinement_settings is None and evaluation.selected is None:
            _raise_unresolved_complete_domain(
                evaluation.results,
                phase="completion",
            )
        terminal_refinement_used = refinement_settings is not None
        if refinement_settings is not None:
            refinement_state = self._refine(*refinement_settings)
            if refinement_state is not None:
                return refinement_state
            complete_domain_optimal = True

        return DomainContinuationState(
            self.current_domain,
            self.current_solution,
            self.current_witness,
            complete_domain_optimal=complete_domain_optimal,
            terminal_refinement_used=terminal_refinement_used,
            bb_lin_fallback_used=self.bb_lin_fallback_used,
        )

    def _refine(
        self,
        refinement_mode: str,
        refinement_strategy: str,
    ) -> DomainContinuationState | None:
        """Certify the retained complete-domain objective with a portfolio."""

        def announce_refinement(candidate_count: int) -> None:
            console.print_debug(
                "refining complete domain with solver portfolio "
                f"(mode={refinement_mode}, "
                f"strategy={refinement_strategy}, "
                f"candidates={candidate_count})",
                flush=True,
            )

        evaluation = self._run_new_wave(
            phase="refinement",
            base_domain=self.current_domain,
            target_size=len(self.complete_domain),
            witness=self.current_witness,
            clingo_mode=refinement_mode,
            clingo_strategy=refinement_strategy,
            patience_seconds=0.0,
            announce=announce_refinement,
        )
        if evaluation is None:
            raise RuntimeError("domain refinement produced no candidates")
        if evaluation.selected is not None:
            self._adopt_candidate(evaluation.selected)

        if evaluation.selected is None and evaluation.counts["unsat"]:
            return DomainContinuationState(
                self.current_domain,
                self.current_solution,
                self.current_witness,
                complete_domain_unsat=True,
                terminal_refinement_used=True,
            )
        if evaluation.selected is None:
            _raise_unresolved_complete_domain(
                evaluation.results,
                phase="refinement",
            )
        if not evaluation.selected.optimum_certified:
            raise RuntimeError(
                "complete-domain refinement ended without an optimum certificate"
            )
        return None

    def _refresh_unresolved(
        self,
        evaluation: _EvaluatedDomainWave,
        *,
        base_domain: Collection[str],
        target_size: int,
        witness: Iterable[str],
        evaluated_domains: set[frozenset[str]],
        enabled: bool,
    ) -> tuple[_EvaluatedDomainWave, int, bool]:
        """Retry entirely unresolved waves at the same domain size."""

        refresh_count = 0
        refresh_space_exhausted = False
        while (
            evaluation.selected is None
            and evaluation.results
            and evaluation.counts["sat"] == 0
            and evaluation.counts["unsat"] == 0
            and enabled
            and refresh_count < self.max_domain_refreshes
        ):

            def announce_refresh(_candidate_count: int) -> None:
                console.print_debug(
                    "refreshing unresolved domain "
                    f"(attempt={refresh_count + 1}/"
                    f"{self.max_domain_refreshes}, "
                    f"size={target_size})",
                    flush=True,
                )

            refreshed = self._run_new_wave(
                phase="refresh",
                base_domain=base_domain,
                target_size=target_size,
                witness=witness,
                excluded_domains=evaluated_domains,
                announce=announce_refresh,
            )
            if refreshed is None:
                refresh_space_exhausted = True
                break

            refresh_count += 1
            evaluated_domains.update(
                candidate.nodes for candidate in refreshed.candidates
            )
            evaluation = refreshed

        return evaluation, refresh_count, refresh_space_exhausted

    def _run_new_wave(
        self,
        *,
        phase: DomainPhase,
        base_domain: Collection[str],
        target_size: int,
        witness: Iterable[str],
        excluded_domains: Collection[Collection[str]] = (),
        clingo_mode: str | None = None,
        clingo_strategy: str | None = None,
        patience_seconds: float | None = None,
        announce: Callable[[int], None] | None = None,
    ) -> _EvaluatedDomainWave | None:
        """Build, solve and classify the next deterministic candidate wave."""

        next_wave = self.wave + 1
        candidates = build_candidate_wave(
            self.complete_domain,
            base_domain,
            target_size=target_size,
            jobs=self.jobs,
            seed=self.seed,
            clause_bound=self.max_clause,
            wave=next_wave,
            excluded_domains=excluded_domains,
        )
        if not candidates:
            return None

        self.wave = next_wave
        if announce is not None:
            announce(len(candidates))
        results = run_domain_wave(
            self.bo,
            candidates,
            phase=phase,
            wave=self.wave,
            max_clause=self.max_clause,
            witness=witness,
            incumbent_solution=self.current_solution,
            clingo_mode=(self.wave_clingo_mode if clingo_mode is None else clingo_mode),
            clingo_strategy=(
                self.wave_clingo_strategy
                if clingo_strategy is None
                else clingo_strategy
            ),
            clingo_configuration=self.clingo_configuration,
            patience_seconds=(
                self.domain_patience_seconds
                if patience_seconds is None
                else patience_seconds
            ),
            clause_patience=self.clause_patience,
            deadline=self.deadline,
            important_nodes=self.important_nodes,
            memory_limit=self.memory_limit,
            on_model=self.on_model,
            memory_estimator=self.memory_estimator,
        )
        selected = select_best_candidate(results, self.important_nodes)
        print_domain_wave_summary(
            phase=phase,
            max_clause=self.max_clause,
            wave=self.wave,
            results=results,
            selected=selected,
        )
        return _EvaluatedDomainWave(
            candidates=candidates,
            results=results,
            selected=selected,
            counts=outcome_counts(results),
        )

    def _adopt_candidate(self, selected: DomainCandidateResult) -> None:
        """Retain one candidate domain without regressing the best witness."""

        selected_objective = solution_objective(
            selected.solution,
            self.important_nodes,
        )
        current_objective = solution_objective(
            self.current_solution,
            self.important_nodes,
        )
        self.current_domain = selected.candidate.nodes
        if selected_objective >= current_objective:
            self.current_solution = selected.solution
            self.current_witness = selected.witness
        self.on_selected(
            self.current_domain,
            self.current_solution,
            self.current_witness,
        )

    def _switch_to_fallback(self, *, reason: str, domain_size: int) -> bool:
        """Switch a stalled continuation to the complementary solver."""

        fallback_settings = stalled_domain_solver_settings(
            self.wave_clingo_mode,
            self.wave_clingo_strategy,
        )
        if fallback_settings is None:
            return False

        self.wave_clingo_mode, self.wave_clingo_strategy = fallback_settings
        self.bb_lin_fallback_used = True
        self.minimum_fallback_retry = True
        console.print_info(
            "switching domain continuation solver "
            f"(reason={reason}, "
            f"max clauses={self.max_clause}, "
            f"mode={self.wave_clingo_mode}, "
            f"strategy={self.wave_clingo_strategy}, "
            f"domain={domain_size})",
            flush=True,
        )
        return True


def continue_domain_at_clause_bound(
    bo: bonesis.BoNesis,
    *,
    max_clause: int,
    initial_domain: Iterable[str],
    initial_solution: Iterable[str],
    initial_witness: Iterable[str],
    expansion_only: bool,
    required_nodes: set[str],
    important_nodes: set[str],
    jobs: int,
    seed: int,
    clingo_mode: str,
    clingo_strategy: str,
    clingo_configuration: str | None,
    domain_patience_seconds: float,
    minimum_domain_yield: float,
    max_domain_refreshes: int,
    clause_patience: SolverPatience,
    deadline: SolverDeadline,
    memory_limit: int | None,
    on_model: Callable[[frozenset[str], Sequence[str], Sequence[str]], bool],
    on_selected: Callable[[frozenset[str], Sequence[str], Sequence[str]], None],
    memory_estimator: DomainMemoryEstimator | None = None,
) -> DomainContinuationState:
    """Acquire or expand a witness at one clause bound."""

    return DomainContinuationRunner(
        bo,
        max_clause=max_clause,
        initial_domain=initial_domain,
        initial_solution=initial_solution,
        initial_witness=initial_witness,
        expansion_only=expansion_only,
        required_nodes=required_nodes,
        important_nodes=important_nodes,
        jobs=jobs,
        seed=seed,
        clingo_mode=clingo_mode,
        clingo_strategy=clingo_strategy,
        clingo_configuration=clingo_configuration,
        domain_patience_seconds=domain_patience_seconds,
        minimum_domain_yield=minimum_domain_yield,
        max_domain_refreshes=max_domain_refreshes,
        clause_patience=clause_patience,
        deadline=deadline,
        memory_limit=memory_limit,
        on_model=on_model,
        on_selected=on_selected,
        memory_estimator=memory_estimator,
    ).run()
