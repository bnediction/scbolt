#!/usr/bin/env python

import argparse
import os
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock
from typing import Any, Callable, Iterable, Mapping, Sequence

import bonesis
import clingo
from bonesis.asp_encoding import clingo_encode
from _domain_continuation import (
    DomainCandidate,
    DomainCandidateResult,
    DomainWaveLeader,
    bounded_midpoint,
    build_candidate_wave,
    continuation_base_domain,
    domain_expansion_gains,
    expansion_domain_size,
    initial_domain_size,
    minimum_domain_gain,
    outcome_counts,
    select_best_candidate,
    solution_objective,
)
from _witness import (
    apply_structural_witness_heuristics,
    read_structural_witness,
    structural_witness,
    structural_witness_clause_bound,
    structural_witness_nodes,
)
from utils import (
    TQDM_TO_TTY,
    add_bonesis_arguments,
    apply_bonesis_mode,
    get_node_sets,
    initialize_bonesis,
    next_solution,
    print_solver_options,
    print_node_reference,
    ptqdm,
)

from scbolt import cli, console
from scbolt.runtime import (
    SolverDeadline,
    SolverPatience,
    SolverPatienceExpired,
    SolverTimeout,
    exit_solver_timeout,
    format_duration,
    parse_solver_timeout,
    reset_solver_timeout_status,
)

bonesis.settings["quiet"] = True
script_name = Path(__file__).name


def parse_min_domain_yield(value: str) -> float:
    """Parse a half-open unit-interval domain-yield threshold."""

    try:
        minimum_yield = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "expected a numeric value greater than or equal to 0 and below 1"
        ) from error
    if not 0 <= minimum_yield < 1:
        raise argparse.ArgumentTypeError(
            "expected a value greater than or equal to 0 and below 1"
        )
    return minimum_yield


def read_gene_list(file: str | Path | None) -> list[str]:
    """Read one gene name per non-empty line."""

    if file is None:
        return []
    with open(file) as stream:
        return [line.rstrip() for line in stream if line.rstrip()]


def _format_progress_ratio(value: int, total: int) -> str:
    """Align a progress value to the width of its expected total."""

    return f"{value:>{len(str(total))}}/{total}"


def _format_solution_objective(
    objective: tuple[int, int],
    *,
    node_total: int,
    important_total: int,
) -> str:
    """Format the retained node-selection objective for a durable message."""

    important, total = objective
    summary = f"solution={total}/{node_total}"
    if important_total:
        summary += f" (important={important}/{important_total})"
    return summary


def _filter_nodes_objective(
    score: Sequence[int],
    *,
    has_important_nodes: bool,
) -> tuple[int, int]:
    """Normalize one Clingo node-selection score for comparisons."""

    values = [abs(int(value)) for value in score]
    if has_important_nodes and len(values) >= 2:
        return values[0], values[1]
    if values:
        return 0, values[-1]
    return 0, 0


def make_filter_nodes_score_formatter(
    important_total: int,
    node_total: int,
) -> Callable[[Sequence[int]], Mapping[str, str]]:
    """Create the progress score formatter used during node selection."""

    def format_score(score: Sequence[int]) -> Mapping[str, str]:
        important, total = _filter_nodes_objective(
            score,
            has_important_nodes=bool(important_total),
        )
        fields = {}

        if important_total:
            fields["important"] = _format_progress_ratio(
                important,
                important_total,
            )
            fields["total"] = _format_progress_ratio(total, node_total)
        elif len(score):
            fields["total"] = _format_progress_ratio(total, node_total)

        return fields or {"score": str(list(score))}

    return format_score


class InheritedObjectiveProgress(ptqdm):
    """Keep a retained node-selection objective visible until it improves."""

    def __init__(
        self,
        *args,
        inherited_objective: tuple[int, int],
        has_important_nodes: bool,
        score_formatter: Callable[[Sequence[int]], Mapping[str, str]],
        **kwargs,
    ) -> None:
        self._displayed_objective = inherited_objective
        self._has_important_nodes = has_important_nodes
        self._inherited_score_formatter = score_formatter
        super().__init__(*args, **kwargs)

    def set_postfix(self, ordered_dict=None, refresh=True, **kwargs) -> None:
        if ordered_dict is not None and "score" in ordered_dict:
            observed = _filter_nodes_objective(
                ordered_dict["score"],
                has_important_nodes=self._has_important_nodes,
            )
            self._displayed_objective = max(
                self._displayed_objective,
                observed,
            )
            important, total = self._displayed_objective
            score = (important, total) if self._has_important_nodes else (total,)
            ordered_dict = {
                key: value
                for key, value in ordered_dict.items()
                if key != "score"
            }
            ordered_dict.update(self._inherited_score_formatter(score))
        super().set_postfix(ordered_dict, refresh=refresh, **kwargs)


def make_filter_consts_score_formatter(
    node_total: int,
    important_total: int = 0,
) -> Callable[[Sequence[int]], Mapping[str, str]]:
    """Create the progress score formatter used during constant selection."""

    def format_score(score: Sequence[int]) -> Mapping[str, str]:
        values = [abs(int(value)) for value in score]
        if not values:
            return {"score": str(list(score))}

        removed_nodes = (
            values[-2] if important_total and len(values) >= 2 else values[-1]
        )
        kept_nodes = max(node_total - removed_nodes, 0)
        fields = {"total": _format_progress_ratio(kept_nodes, node_total)}
        if important_total and len(values) >= 2:
            fields = {
                "important": _format_progress_ratio(
                    values[-1],
                    important_total,
                ),
                **fields,
            }
        return fields

    return format_score


def get_clingo_options(configuration=None, *extra_options):
    """Build raw Clingo options for selection views."""

    options = []
    if configuration:
        options.append(f"--configuration={configuration}")
    options.extend(option for option in extra_options if option)
    return options


def get_filter_clingo_options(
    mode,
    strategy,
    configuration=None,
    *extra_options,
):
    """Build optimization options for a selection view."""

    options = get_clingo_options(configuration)
    if mode == "opt":
        options.extend(["--opt-mode=opt", f"--opt-strategy={strategy}"])
    elif mode.startswith("enum,"):
        options.append(f"--opt-mode={mode}")
    elif mode == "ignore":
        options.append("--opt-mode=ignore")
    options.extend(option for option in extra_options if option)
    return options


def get_filter_clingo_settings(
    mode,
    strategy,
    configuration=None,
    *extra_options,
):
    """Return BoNesis settings containing selection-specific Clingo options."""

    options = get_filter_clingo_options(
        mode,
        strategy,
        configuration,
        *extra_options,
    )
    return {"clingo_options": options} if options else {}


def format_node_coverage(name, kept, total):
    """Format retained and removed node counts."""

    removed = total - kept
    pct = 0 if total == 0 else 100 * kept / total
    return f"{name}: kept={kept}/{total} ({pct:.1f}%), removed={removed}"


def print_node_solution(solution, nodes_in_data, nodes_in_domain, **kwargs):
    """Print node-selection coverage against data and domain nodes."""

    solution = set(solution)
    console.print_result(f"solution: nodes={len(solution)}", **kwargs)
    console.print_result(
        format_node_coverage(
            "data",
            len(nodes_in_data & solution),
            len(nodes_in_data),
        ),
        **kwargs,
    )
    console.print_result(
        format_node_coverage(
            "domain",
            len(nodes_in_domain & solution),
            len(nodes_in_domain),
        ),
        **kwargs,
    )


def write_lines(lines: Iterable[str], file: Path) -> None:
    """Atomically write normalized lines to a text file."""

    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(f".{file.name}.tmp")
    with open(temporary, "w") as stream:
        for line in lines:
            stream.write(f"{line}\n")
    os.replace(temporary, file)


def write_node_solution(nodes: Iterable[str], file: Path) -> None:
    """Write one selected node per line."""

    write_lines(nodes, file)


def write_structural_witness(witness: Iterable[str], file: Path) -> None:
    """Write an executable structural witness as ASP facts."""

    write_lines((f"{atom}." for atom in sorted(set(witness))), file)


def clause_continuation_bounds(
    max_clauses: int,
    lower_bound: int = 1,
) -> tuple[int, ...]:
    """Return increasing clause bounds compatible with the initial witness."""

    if max_clauses < 1:
        raise ValueError("`max_clauses` must be greater than or equal to 1")
    if lower_bound < 1:
        raise ValueError("`lower_bound` must be greater than or equal to 1")
    if lower_bound > max_clauses:
        raise ValueError(
            "initial structural witness requires "
            f"max_clauses >= {lower_bound} (got {max_clauses})"
        )

    return tuple(range(lower_bound, max_clauses + 1))


def make_no_solution_error(
    clause_continuation: bool,
    parameter: str | None = None,
) -> RuntimeError:
    """Create an actionable error for an unsuccessful node selection."""

    opposite = "false" if clause_continuation else "true"
    if parameter is not None:
        suggestion = f"with {parameter}={opposite}"
    elif clause_continuation:
        suggestion = "without --clause-continuation"
    else:
        suggestion = "with --clause-continuation"

    return RuntimeError(f"no solution found (please try {suggestion})")


def fork_bonesis(
    bo: bonesis.BoNesis,
    *,
    max_clause: int,
    domain_nodes: Iterable[str] | None = None,
    witness: Iterable[str] = (),
) -> bonesis.BoNesis:
    """Create an independent BoNesis problem for one solver attempt."""

    domain_options = dict(bo.domain.options)
    domain_options["maxclause"] = max_clause
    graph = bo.domain
    if domain_nodes is not None:
        graph = bo.domain.subgraph(tuple(domain_nodes))
    domain = bonesis.domains.InfluenceGraph(graph, **domain_options)
    stage = bonesis.BoNesis(domain, bo.data)
    stage.manager.reset_from(bo.manager)

    apply_structural_witness_heuristics(stage, witness)

    return stage


def make_stage_progress(
    description: str,
    inherited_objective: tuple[int, int],
    score_formatter: Callable[[Sequence[int]], Mapping[str, str]],
    *,
    has_important_nodes: bool,
):
    """Create a progress factory with a stage-specific description."""

    important, total = inherited_objective
    inherited_score = (
        (important, total) if has_important_nodes else (total,)
    )
    initial_postfix = score_formatter(inherited_score)

    def progress(*args, **kwargs):
        kwargs["desc"] = description
        kwargs["postfix"] = initial_postfix
        kwargs.setdefault(
            "bar_format",
            "{desc}: {n_fmt}it ({elapsed}{postfix})",
        )
        return InheritedObjectiveProgress(
            *args,
            inherited_objective=inherited_objective,
            has_important_nodes=has_important_nodes,
            score_formatter=score_formatter,
            **kwargs,
        )

    return progress


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

    def close(self) -> None:
        self.events.put(("close", self.candidate_index))


class ActiveCandidateViews:
    """Track active views so the coordinator can interrupt a complete wave."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._views = {}
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

    def interrupt_all(self) -> None:
        with self._lock:
            self._interrupted = True
            views = tuple(self._views.values())
        for view in views:
            try:
                view.interrupt()
            except (AttributeError, RuntimeError):
                pass


def solve_domain_candidate(
    bo: bonesis.BoNesis,
    candidate: DomainCandidate,
    *,
    max_clause: int,
    witness: Iterable[str],
    clingo_opt_mode: str,
    clingo_opt_strategy: str,
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
    extra_clingo_options = ["--heuristic=Domain"] if witness else []
    view_settings = get_filter_clingo_settings(
        clingo_opt_mode,
        clingo_opt_strategy,
        clingo_configuration,
        *extra_clingo_options,
    )
    view_settings["parallel"] = 1
    view = bonesis.NodesView(
        stage_bo,
        mode=clingo_opt_mode,
        extra=structural_witness,
        intermediate_model_cb=intermediate_solution,
        clingo_opt_strategy=clingo_opt_strategy,
        progress=progress,
        **view_settings,
    )
    if not active_views.register(candidate.index, view):
        return DomainCandidateResult(candidate, "cancelled")

    outcome = "sat"
    solution = ()
    structural_model = ()
    try:
        solution, structural_model = next_solution(view)
    except StopIteration:
        outcome = "cancelled" if cancelled.is_set() else "unsat"
    except RuntimeError:
        if not cancelled.is_set():
            raise
        outcome = "cancelled"
        if best_model[0] is not None:
            solution, structural_model = best_model[0]
    finally:
        active_views.unregister(candidate.index)

    return DomainCandidateResult(
        candidate=candidate,
        outcome=outcome,
        solution=tuple(sorted(solution)),
        witness=tuple(structural_model),
    )


def run_domain_wave(
    bo: bonesis.BoNesis,
    candidates: Sequence[DomainCandidate],
    *,
    phase: str,
    wave: int,
    max_clause: int,
    witness: Iterable[str],
    incumbent_solution: Iterable[str],
    clingo_opt_mode: str,
    clingo_opt_strategy: str,
    clingo_configuration: str | None,
    patience_seconds: float,
    clause_patience: SolverPatience,
    deadline: SolverDeadline,
    important_nodes: set[str],
    on_model: Callable[[frozenset[str], Sequence[str], Sequence[str]], bool],
) -> tuple[DomainCandidateResult, ...]:
    """Evaluate one domain wave while rendering all progress in the parent."""

    if not candidates:
        return ()

    progress_stream = sys.stdout
    close_progress_stream = False
    if TQDM_TO_TTY:
        try:
            progress_stream = open("/dev/tty", "w")
            close_progress_stream = True
        except OSError:
            pass

    progress_cursor_saved = False
    progress_options = {}
    if progress_stream.isatty():
        try:
            terminal_rows = os.get_terminal_size(progress_stream.fileno()).lines
        except OSError:
            terminal_rows = len(candidates) + 1
        progress_rows = min(len(candidates), max(1, terminal_rows - 1))
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

    def format_candidate_objective(candidate_index: int) -> Mapping[str, str]:
        """Format the best inherited or locally observed candidate score."""

        important, total = displayed_objectives[candidate_index]
        score = (
            (important, total)
            if important_nodes
            else (total,)
        )
        return score_formatters[candidate_index](score)

    candidate_width = len(str(len(candidates)))
    bars = {
        candidate.index: ptqdm(
            total=float("inf"),
            desc=(
                f"Domain {phase} [max clauses={max_clause}, wave={wave}, "
                f"candidate={candidate.index:>{candidate_width}}/"
                f"{len(candidates)}, "
                f"nodes={len(candidate.nodes)}]"
            ),
            postfix=format_candidate_objective(candidate.index),
            position=position,
            file=progress_stream,
            bar_format="{desc}: {n_fmt:>4}it ({elapsed}{postfix})",
            **progress_options,
        )
        for position, candidate in enumerate(candidates)
    }
    progress_display_closed = False

    def close_progress_display() -> None:
        """Clear the complete multi-bar display exactly once."""

        nonlocal progress_display_closed
        if progress_display_closed:
            return
        progress_display_closed = True

        for bar in reversed(tuple(bars.values())):
            bar.close()

        if progress_cursor_saved:
            # Restore the stable anchor saved before tqdm allocated its bars,
            # then erase the complete transient display in one operation.
            progress_stream.write("\033[u\r\033[J")
            progress_stream.flush()

        if close_progress_stream:
            progress_stream.close()

    candidate_by_index = {
        candidate.index: candidate for candidate in candidates
    }
    observed_models = {}
    wave_patience = SolverPatience(patience_seconds)
    wave_leader = DomainWaveLeader()
    stop_reason = None
    executor = ThreadPoolExecutor(
        max_workers=len(candidates),
        thread_name_prefix="scbolt-domain",
    )
    futures = {
        executor.submit(
            solve_domain_candidate,
            bo,
            candidate,
            max_clause=max_clause,
            witness=witness,
            clingo_opt_mode=clingo_opt_mode,
            clingo_opt_strategy=clingo_opt_strategy,
            clingo_configuration=clingo_configuration,
            events=events,
            active_views=active_views,
            cancelled=cancelled,
        ): candidate
        for candidate in candidates
    }
    pending = set(futures)

    def process_event(event) -> None:
        kind, candidate_index, *payload = event
        bar = bars[candidate_index]
        if kind == "postfix":
            values = payload[0]
            if "score" in values:
                objective = _filter_nodes_objective(
                    values["score"],
                    has_important_nodes=bool(important_nodes),
                )
                if objective > displayed_objectives[candidate_index]:
                    displayed_objectives[candidate_index] = objective
                values = format_candidate_objective(candidate_index)
            bar.set_postfix(values, refresh=False)
        elif kind == "update":
            bar.update(payload[0])
        elif kind == "refresh":
            bar.refresh()
        elif kind == "model":
            solution, structural_model = payload
            observed_models[candidate_index] = DomainCandidateResult(
                candidate=candidate_by_index[candidate_index],
                outcome="sat",
                solution=solution,
                witness=structural_model,
            )
            if wave_leader.update(
                candidate_index,
                solution,
                important_nodes,
            ):
                wave_patience.reset()
            if on_model(
                candidate_by_index[candidate_index].nodes,
                solution,
                structural_model,
            ):
                clause_patience.reset()

    try:
        while pending:
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

            remaining = deadline.remaining()
            if remaining is not None and remaining <= 0:
                stop_reason = "timeout"
            else:
                patience_remaining = clause_patience.remaining()
                if patience_remaining is not None and patience_remaining <= 0:
                    stop_reason = "clause-patience"
                else:
                    patience_remaining = wave_patience.remaining()
                    if (
                        patience_remaining is not None
                        and patience_remaining <= 0
                    ):
                        stop_reason = "domain-patience"

            if stop_reason is not None:
                cancelled.set()
                active_views.interrupt_all()

            done, pending = wait(
                pending,
                timeout=0,
                return_when=FIRST_COMPLETED,
            )
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
            if candidate.index in observed_models and result.outcome == "cancelled":
                result = observed_models[candidate.index]
            elif stop_reason == "domain-patience" and result.outcome == "cancelled":
                result = DomainCandidateResult(candidate, "unknown")
            results.append(result)
    finally:
        close_progress_display()
        cancelled.set()
        active_views.interrupt_all()
        executor.shutdown(wait=True, cancel_futures=True)

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
    outcomes = [
        f"sat={counts['sat']}",
        f"unsat={counts['unsat']}",
        f"unknown={counts['unknown']}",
    ]
    if counts["cancelled"]:
        outcomes.append(f"cancelled={counts['cancelled']}")
    if selected is not None:
        result = (
            f"solution={len(selected.solution)}/"
            f"{len(selected.candidate.nodes)}"
        )
    else:
        result = "no solution"
    console.print_info(
        f"domain continuation [{', '.join(context)}]: "
        f"{result} ({', '.join(outcomes)})",
        flush=True,
    )


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
    clingo_opt_mode: str,
    clingo_opt_strategy: str,
    clingo_configuration: str | None,
    domain_patience_seconds: float,
    minimum_domain_yield: float,
    max_domain_refreshes: int,
    clause_patience: SolverPatience,
    deadline: SolverDeadline,
    on_model: Callable[[frozenset[str], Sequence[str], Sequence[str]], bool],
    on_selected: Callable[[frozenset[str], Sequence[str], Sequence[str]], None],
) -> DomainContinuationState:
    """Acquire or only expand a witness at one clause bound."""

    complete_domain = frozenset(bo.domain.nodes)
    current_domain = frozenset(initial_domain)
    current_solution = tuple(sorted(initial_solution))
    current_witness = tuple(initial_witness)
    wave = 0

    if not current_domain:
        current_domain = frozenset(required_nodes & complete_domain)
    if not current_domain <= complete_domain:
        raise ValueError("initial continuation domain exceeds the complete domain")
    if expansion_only and (not current_solution or not current_witness):
        raise ValueError(
            "expansion-only domain continuation requires an initial "
            "structural witness with selected nodes"
        )

    if not current_witness:
        minimum_size = len(current_domain)
        lower_unsat = minimum_size - 1
        upper_unknown = len(complete_domain) + 1
        target_size = initial_domain_size(minimum_size, len(complete_domain))

        while not current_witness:
            wave += 1
            candidates = build_candidate_wave(
                complete_domain,
                current_domain,
                target_size=target_size,
                jobs=jobs,
                seed=seed,
                clause_bound=max_clause,
                wave=wave,
            )
            results = run_domain_wave(
                bo,
                candidates,
                phase="acquisition",
                wave=wave,
                max_clause=max_clause,
                witness=(),
                incumbent_solution=current_solution,
                clingo_opt_mode=clingo_opt_mode,
                clingo_opt_strategy=clingo_opt_strategy,
                clingo_configuration=clingo_configuration,
                patience_seconds=domain_patience_seconds,
                clause_patience=clause_patience,
                deadline=deadline,
                important_nodes=important_nodes,
                on_model=on_model,
            )
            selected = select_best_candidate(results, important_nodes)
            print_domain_wave_summary(
                phase="acquisition",
                max_clause=max_clause,
                wave=wave,
                results=results,
                selected=selected,
            )
            if selected is not None:
                current_domain = selected.candidate.nodes
                current_solution = selected.solution
                current_witness = selected.witness
                on_selected(
                    current_domain,
                    current_solution,
                    current_witness,
                )
                break

            counts = outcome_counts(results)
            if target_size == len(complete_domain) and counts["unsat"]:
                return DomainContinuationState(
                    current_domain,
                    current_solution,
                    current_witness,
                    complete_domain_unsat=True,
                )

            if results and counts["unsat"] == len(results):
                lower_unsat = max(lower_unsat, target_size)
                upper = min(upper_unknown - 1, len(complete_domain))
                if lower_unsat < upper:
                    target_size = bounded_midpoint(lower_unsat, upper)
                else:
                    target_size = min(len(complete_domain), target_size + 1)
                continue

            if counts["unknown"]:
                upper_unknown = min(upper_unknown, target_size)
                lower = max(minimum_size, lower_unsat + 1)
                upper = upper_unknown - 1
                if lower <= upper:
                    target_size = bounded_midpoint(lower, upper)
                else:
                    target_size = max(minimum_size, min(target_size, upper_unknown))
                continue

            raise RuntimeError("domain continuation ended without a solver outcome")

    def adopt_candidate(selected: DomainCandidateResult) -> None:
        """Retain one candidate domain without regressing the best witness."""

        nonlocal current_domain, current_solution, current_witness

        selected_objective = solution_objective(
            selected.solution,
            important_nodes,
        )
        current_objective = solution_objective(
            current_solution,
            important_nodes,
        )
        current_domain = selected.candidate.nodes
        if selected_objective >= current_objective:
            current_solution = selected.solution
            current_witness = selected.witness
        on_selected(
            current_domain,
            current_solution,
            current_witness,
        )

    expansion_target = expansion_domain_size(
        len(current_domain),
        len(complete_domain),
    )
    while expansion_target < len(complete_domain):
        expansion_base_domain = current_domain
        expansion_base_solution = current_solution
        expansion_size = expansion_target - len(expansion_base_domain)
        required_gain = minimum_domain_gain(
            expansion_size,
            minimum_domain_yield,
        )
        evaluated_domains: set[frozenset[str]] = set()

        wave += 1
        candidates = build_candidate_wave(
            complete_domain,
            expansion_base_domain,
            target_size=expansion_target,
            jobs=jobs,
            seed=seed,
            clause_bound=max_clause,
            wave=wave,
        )
        evaluated_domains.update(candidate.nodes for candidate in candidates)
        results = run_domain_wave(
            bo,
            candidates,
            phase="expansion",
            wave=wave,
            max_clause=max_clause,
            witness=current_witness,
            incumbent_solution=current_solution,
            clingo_opt_mode=clingo_opt_mode,
            clingo_opt_strategy=clingo_opt_strategy,
            clingo_configuration=clingo_configuration,
            patience_seconds=domain_patience_seconds,
            clause_patience=clause_patience,
            deadline=deadline,
            important_nodes=important_nodes,
            on_model=on_model,
        )
        selected = select_best_candidate(results, important_nodes)
        print_domain_wave_summary(
            phase="expansion",
            max_clause=max_clause,
            wave=wave,
            results=results,
            selected=selected,
        )
        if selected is None:
            reduced_step = max(1, expansion_size // 2)
            expansion_target = len(expansion_base_domain) + reduced_step
            continue

        adopt_candidate(selected)
        important_gain, retained_gain = domain_expansion_gains(
            expansion_base_solution,
            current_solution,
            important_nodes,
        )
        refresh_count = 0
        refresh_space_exhausted = False

        while (
            minimum_domain_yield > 0
            and important_gain == 0
            and retained_gain < required_gain
            and refresh_count < max_domain_refreshes
        ):
            refresh_core = expansion_base_domain | frozenset(current_solution)
            next_wave = wave + 1
            candidates = build_candidate_wave(
                complete_domain,
                refresh_core,
                target_size=expansion_target,
                jobs=jobs,
                seed=seed,
                clause_bound=max_clause,
                wave=next_wave,
                excluded_domains=evaluated_domains,
            )
            if not candidates:
                refresh_space_exhausted = True
                break

            wave = next_wave
            refresh_count += 1
            evaluated_domains.update(candidate.nodes for candidate in candidates)
            protected_additions = len(refresh_core - expansion_base_domain)
            console.print_debug(
                "refreshing domain "
                f"(attempt={refresh_count}/{max_domain_refreshes}, "
                f"size={expansion_target}, "
                f"yield={retained_gain}/{expansion_size} "
                f"[{retained_gain / expansion_size:.1%} < "
                f"{minimum_domain_yield:.1%}], "
                f"protected={protected_additions})",
                flush=True,
            )
            results = run_domain_wave(
                bo,
                candidates,
                phase="refresh",
                wave=wave,
                max_clause=max_clause,
                witness=current_witness,
                incumbent_solution=current_solution,
                clingo_opt_mode=clingo_opt_mode,
                clingo_opt_strategy=clingo_opt_strategy,
                clingo_configuration=clingo_configuration,
                patience_seconds=domain_patience_seconds,
                clause_patience=clause_patience,
                deadline=deadline,
                important_nodes=important_nodes,
                on_model=on_model,
            )
            selected = select_best_candidate(results, important_nodes)
            print_domain_wave_summary(
                phase="refresh",
                max_clause=max_clause,
                wave=wave,
                results=results,
                selected=selected,
            )
            if selected is not None:
                adopt_candidate(selected)
            important_gain, retained_gain = domain_expansion_gains(
                expansion_base_solution,
                current_solution,
                important_nodes,
            )

        if (
            minimum_domain_yield > 0
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
                    f"(gain={gain}, minimum={minimum_domain_yield:.1%}, "
                    f"domains tested={len(evaluated_domains)}); "
                    "expanding domain",
                    flush=True,
                )
            elif refresh_count == max_domain_refreshes:
                console.print_warning(
                    "minimum domain yield not reached before refresh limit "
                    f"(gain={gain}, minimum={minimum_domain_yield:.1%}, "
                    f"refreshes={refresh_count}); expanding domain",
                    flush=True,
                )

        expansion_target = expansion_domain_size(
            len(current_domain),
            len(complete_domain),
        )

    return DomainContinuationState(
        current_domain,
        current_solution,
        current_witness,
    )


parser_description = """Select Boolean network components using BoNesis.

Two actions are proposed:
    - filter-nodes:
        component selection maximizing variable number while constraining
        Boolean networks to satisfy the observations
    - filter-consts:
        component selection removing strong constants while constraining
        Boolean networks to satisfy the observations

See Chevalier et al. (2024):
https://hal.science/hal-04629083/document
"""

parser = argparse.ArgumentParser(
    prog="select",
    description=parser_description,
    usage=(
        f"python {script_name} [filter-nodes | filter-consts] " "<FILE> <FILE> [<args>]"
    ),
    formatter_class=cli.HelpFormatter,
)
parser.add_argument(
    "action",
    choices=["filter-nodes", "filter-consts"],
    metavar="[filter-nodes | filter-consts]",
    help="BoNesis gene-selection action to run",
)
add_bonesis_arguments(parser)
parser.add_argument(
    "--important-nodes",
    dest="important_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help=(
        "input file storing important nodes prioritized to appear "
        "(format: json or txt)"
    ),
)
parser.add_argument(
    "--mandatory-nodes",
    dest="mandatory_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help=(
        "input file storing mandatory nodes forced to appear " "(format: json or txt)"
    ),
)
parser.add_argument(
    "--forbidden-nodes",
    dest="forbidden_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="input file storing nodes excluded from the regulatory domain",
)
parser.add_argument(
    "--domain-size-file",
    dest="domain_size_file",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="optional output storing the full domain size",
)
parser.add_argument(
    "--clingo-configuration",
    dest="clingo_configuration",
    type=str,
    required=False,
    default=None,
    metavar="[auto | frumpy | jumpy | tweety | handy | crafty | trendy | many | FILE]",
    help=(
        "Clingo default configuration passed as --configuration; if not "
        "specified, BoNesis/Clingo defaults are used"
    ),
)
parser.add_argument(
    "--clingo-opt-strategy",
    dest="clingo_opt_strategy",
    action=cli.Clingo_opt_strategy,
    required=False,
)
parser.add_argument(
    "--clause-continuation",
    dest="clause_continuation",
    action="store_true",
    help=(
        "solve increasing clause bounds and reuse each structural witness "
        "as a soft heuristic"
    ),
)
parser.add_argument(
    "--clause-bound-patience",
    dest="clause_bound_patience",
    type=parse_solver_timeout,
    required=False,
    default=0.0,
    metavar="DURATION",
    help=(
        "maximum time without a Clingo objective improvement before "
        "continuing to the next intermediate clause bound; suffixes s, m, "
        "h and d are supported, and 0 disables the patience (default: 0)"
    ),
)
parser.add_argument(
    "--clause-continuation-parameter",
    dest="clause_continuation_parameter",
    type=str,
    required=False,
    default=None,
    help=argparse.SUPPRESS,
)
parser.add_argument(
    "--domain-continuation",
    dest="domain_continuation",
    action="store_true",
    help=(
        "search candidate regulatory subdomains in parallel and expand "
        "the selected witness toward the complete domain"
    ),
)
parser.add_argument(
    "--domain-continuation-expansion-only",
    dest="domain_continuation_expansion_only",
    action="store_true",
    help=argparse.SUPPRESS,
)
parser.add_argument(
    "--domain-wave-patience",
    dest="domain_wave_patience",
    type=parse_solver_timeout,
    required=False,
    default=0.0,
    metavar="DURATION",
    help=(
        "maximum time without an improvement of the best portfolio "
        "objective within one domain-continuation wave; suffixes s, m, h "
        "and d are supported, and 0 disables the patience (default: 0)"
    ),
)
parser.add_argument(
    "--min-domain-yield",
    dest="min_domain_yield",
    type=parse_min_domain_yield,
    required=False,
    default=0.10,
    metavar="FLOAT",
    help=(
        "minimum cumulative retained-node gain per node added during domain "
        "expansion; low-yield expansions are refreshed at constant size, "
        "and 0 disables refreshes (default: 0.10)"
    ),
)
parser.add_argument(
    "--max-domain-refreshes",
    dest="max_domain_refreshes",
    type=int,
    required=False,
    default=2,
    metavar="INT",
    help=(
        "maximum number of constant-size domain refreshes before expansion "
        "resumes; 0 disables domain refreshes (default: 2)"
    ),
)
parser.add_argument(
    "--domain-continuation-jobs",
    dest="domain_continuation_jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="maximum candidate domains evaluated simultaneously (default: 1)",
)
parser.add_argument(
    "--domain-continuation-seed",
    dest="domain_continuation_seed",
    type=int,
    required=False,
    default=int(os.getenv("PYTHONHASHSEED", "0")),
    help=argparse.SUPPRESS,
)
parser.add_argument(
    "--initial-witness",
    dest="initial_witness",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help=argparse.SUPPRESS,
)
parser.add_argument(
    "--witness",
    dest="witness",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help=argparse.SUPPRESS,
)

args = parser.parse_args()
if args.domain_continuation_jobs < 1:
    parser.error("--domain-continuation-jobs must be greater than or equal to 1")
if args.max_domain_refreshes < 0:
    parser.error("--max-domain-refreshes must be greater than or equal to 0")
if args.domain_continuation and args.action != "filter-nodes":
    parser.error("--domain-continuation is only available with filter-nodes")
if args.domain_continuation_expansion_only and not args.domain_continuation:
    parser.error(
        "--domain-continuation-expansion-only requires "
        "--domain-continuation"
    )
if args.domain_continuation_expansion_only and args.initial_witness is None:
    parser.error(
        "--domain-continuation-expansion-only requires --initial-witness"
    )
reset_solver_timeout_status(args.timeout_status_file)
if args.witness is None:
    args.witness = args.solution.with_name("witness.lp")

bo, canonical, clingo_parallel_option = initialize_bonesis(
    args,
    allow_skipping_nodes=args.action == "filter-nodes",
    default_canonical=False,
    forbidden_nodes_file=args.forbidden_nodes,
)
new_constraints = apply_bonesis_mode(bo, args.bonesis_mode)

if args.domain_size_file is not None:
    write_lines((str(len(bo.domain.nodes)),), args.domain_size_file)

if args.action == "filter-nodes":
    console.print_task("maximizing satisfiable nodes")

    bo.maximize_nodes()

    mandatory_nodes = read_gene_list(args.mandatory_nodes)
    for node in mandatory_nodes:
        bo.custom(f"node({clingo_encode(node)}).")

    important_nodes = set(read_gene_list(args.important_nodes))
    important_nodes_in_domain = important_nodes & set(bo.domain.nodes)
    for node in important_nodes_in_domain:
        bo.custom(f"important_node({clingo_encode(node)}).")

    bo.custom("#maximize { 1@100,N: important_node(N),node(N) }.")
    filter_nodes_score_formatter = make_filter_nodes_score_formatter(
        important_total=len(important_nodes_in_domain),
        node_total=len(bo.domain.nodes),
    )
    ptqdm.score_formatter = filter_nodes_score_formatter
    ptqdm.initial_postfix = filter_nodes_score_formatter(
        [0, 0] if important_nodes_in_domain else [0]
    )
    nodes_in_data, nodes_in_domain, domain_edges = get_node_sets(bo)
    initial_witness = read_structural_witness(args.initial_witness)
    if args.domain_continuation_expansion_only and not initial_witness:
        parser.error(
            "--domain-continuation-expansion-only requires a non-empty "
            "structural witness"
        )

    if not new_constraints:
        console.print_info("no new constraints added; stopping", flush=True)
        write_node_solution(bo.domain.nodes, args.solution)
        if initial_witness:
            write_structural_witness(initial_witness, args.witness)
        sys.exit(0)

    effective_clingo_opt_strategy = args.clingo_opt_strategy or "bb,dec"
    print_node_reference(
        nodes_in_data,
        nodes_in_domain,
        domain_edges,
        flush=True,
    )
    print_solver_options(
        args.clingo_opt_mode,
        effective_clingo_opt_strategy,
        args.max_clauses,
        canonical,
        configuration=args.clingo_configuration or "auto",
        jobs=args.jobs,
        flush=True,
    )
    initial_witness_clause_bound = structural_witness_clause_bound(initial_witness)
    if initial_witness_clause_bound > args.max_clauses:
        raise ValueError(
            "initial structural witness requires "
            f"max_clauses >= {initial_witness_clause_bound} "
            f"(got {args.max_clauses})"
        )

    bounds = (
        clause_continuation_bounds(
            args.max_clauses,
            lower_bound=initial_witness_clause_bound,
        )
        if args.clause_continuation
        else (args.max_clauses,)
    )
    if args.clause_continuation:
        bounds_text = (
            str(bounds[0])
            if len(bounds) == 1
            else f"{bounds[0]}..{bounds[-1]}"
        )
        console.print_options(
            "clause continuation: "
            f"bounds={bounds_text}, "
            "bound patience="
            f"{format_duration(args.clause_bound_patience)}",
            flush=True,
        )
    else:
        console.print_options("clause continuation: none", flush=True)

    if args.domain_continuation:
        continuation_mode = (
            "expansion"
            if args.domain_continuation_expansion_only
            else "adaptive"
        )
        console.print_options(
            "domain continuation: "
            f"mode={continuation_mode}, "
            f"candidates={args.domain_continuation_jobs}, "
            "candidate threads=1, "
            "wave patience="
            f"{format_duration(args.domain_wave_patience)}, "
            f"minimum yield={args.min_domain_yield:.1%}, "
            f"refresh limit={args.max_domain_refreshes}, "
            f"seed={args.domain_continuation_seed}",
            flush=True,
        )
    else:
        console.print_options("domain continuation: none", flush=True)
    console.print_warning("this may take some time.", flush=True)
    complete_domain = frozenset(bo.domain.nodes)
    required_nodes = (
        set(mandatory_nodes) | important_nodes_in_domain
    ) & complete_domain
    initial_solution = structural_witness_nodes(initial_witness)
    current_witness = initial_witness
    current_domain = (
        continuation_base_domain(
            initial_solution,
            required_nodes,
            complete_domain,
        )
        if args.domain_continuation
        else complete_domain
    )
    solution = tuple(initial_solution)
    retained = {
        "domain": current_domain,
        "solution": solution,
        "witness": current_witness,
        "objective": (
            len(set(solution) & important_nodes_in_domain),
            len(solution),
        ),
    }

    def print_clause_bound_patience_warning(max_clause: int) -> None:
        """Report the best objective retained at an exhausted clause bound."""

        solution_summary = _format_solution_objective(
            retained["objective"],
            node_total=len(complete_domain),
            important_total=len(important_nodes_in_domain),
        )
        console.print_warning(
            "no objective improvement within the clause-bound patience "
            f"[max clauses={max_clause}, "
            f"time={format_duration(args.clause_bound_patience)}]: "
            f"{solution_summary}",
            flush=True,
        )

    def rebase_for_next_clause_bound(nodes):
        """Retain selected and required nodes for the next clause bound."""

        domain = (
            continuation_base_domain(
                nodes,
                required_nodes,
                complete_domain,
            )
            if args.domain_continuation
            else complete_domain
        )
        retained["domain"] = domain
        return domain

    deadline = SolverDeadline(args.timeout)

    for stage_index, max_clause in enumerate(bounds, start=1):
        if stage_index > 1:
            current_domain = rebase_for_next_clause_bound(solution)

        is_target = max_clause == args.max_clauses
        stage_name = "Target optimization" if is_target else "Clause continuation"
        clingo_opt_mode = args.clingo_opt_mode
        clingo_opt_strategy = effective_clingo_opt_strategy
        description = (
            f"{stage_name} [{stage_index}/{len(bounds)}, "
            f"max clauses={max_clause}]"
        )

        stage_patience_seconds = (
            0.0 if is_target else args.clause_bound_patience
        )
        stage_patience = SolverPatience(stage_patience_seconds)
        stage_best = [None]

        def store_model(domain, nodes, witness, *, force=False):
            domain = frozenset(domain)
            nodes = tuple(sorted(nodes))
            witness = tuple(witness)
            objective = (
                len(set(nodes) & important_nodes_in_domain),
                len(nodes),
            )
            improved = objective > retained["objective"]
            if not force and not improved:
                return False

            retained["domain"] = domain
            retained["solution"] = nodes
            retained["witness"] = witness
            retained["objective"] = objective
            write_structural_witness(witness, args.witness)
            write_node_solution(nodes, args.solution)
            return improved

        def retain_model(domain, nodes, witness):
            return store_model(domain, nodes, witness)

        def retain_selected(domain, nodes, witness):
            store_model(domain, nodes, witness, force=True)

        if args.domain_continuation:
            try:
                continuation = continue_domain_at_clause_bound(
                    bo,
                    max_clause=max_clause,
                    initial_domain=current_domain,
                    initial_solution=solution,
                    initial_witness=current_witness,
                    expansion_only=args.domain_continuation_expansion_only,
                    required_nodes=required_nodes,
                    important_nodes=important_nodes_in_domain,
                    jobs=args.domain_continuation_jobs,
                    seed=args.domain_continuation_seed,
                    clingo_opt_mode=clingo_opt_mode,
                    clingo_opt_strategy=clingo_opt_strategy,
                    clingo_configuration=args.clingo_configuration,
                    domain_patience_seconds=args.domain_wave_patience,
                    minimum_domain_yield=args.min_domain_yield,
                    max_domain_refreshes=args.max_domain_refreshes,
                    clause_patience=stage_patience,
                    deadline=deadline,
                    on_model=retain_model,
                    on_selected=retain_selected,
                )
            except SolverTimeout:
                exit_solver_timeout(args.timeout_status_file)
            except SolverPatienceExpired:
                solution = tuple(retained["solution"])
                current_witness = tuple(retained["witness"])
                print_clause_bound_patience_warning(max_clause)
                continue

            if continuation.complete_domain_unsat:
                if is_target:
                    raise make_no_solution_error(
                        args.clause_continuation,
                        args.clause_continuation_parameter,
                    )
                solution = tuple(retained["solution"])
                current_witness = tuple(retained["witness"])
                console.print_warning(
                    "domain continuation proved the complete domain "
                    f"unsatisfiable (max clauses={max_clause}); continuing",
                    flush=True,
                )
                continue

            current_domain = continuation.domain
            solution = continuation.solution
            current_witness = continuation.witness
            if solution and current_witness:
                retain_model(current_domain, solution, current_witness)

        stage_bo = fork_bonesis(
            bo,
            max_clause=max_clause,
            witness=current_witness,
        )

        def intermediate_solution(model):
            stage_best[0] = model
            nodes, witness = model
            if retain_model(complete_domain, nodes, witness):
                stage_patience.reset()

        extra_clingo_options = [clingo_parallel_option]
        if current_witness:
            extra_clingo_options.insert(0, "--heuristic=Domain")
        view_settings = get_filter_clingo_settings(
            clingo_opt_mode,
            clingo_opt_strategy,
            args.clingo_configuration,
            *extra_clingo_options,
        )

        view = bonesis.NodesView(
            stage_bo,
            mode=clingo_opt_mode,
            extra=structural_witness,
            intermediate_model_cb=intermediate_solution,
            clingo_opt_strategy=clingo_opt_strategy,
            progress=make_stage_progress(
                description,
                retained["objective"],
                filter_nodes_score_formatter,
                has_important_nodes=bool(important_nodes_in_domain),
            ),
            **view_settings,
        )
        if is_target:
            view.standalone(output_filename=args.asp)

        try:
            solution, current_witness = next_solution(
                view,
                deadline,
                stage_patience,
            )
        except SolverTimeout:
            exit_solver_timeout(args.timeout_status_file)
        except SolverPatienceExpired:
            if stage_best[0] is not None:
                solution, current_witness = stage_best[0]
            elif retained["solution"]:
                solution = tuple(retained["solution"])
                current_witness = tuple(retained["witness"])
            print_clause_bound_patience_warning(max_clause)
            continue
        except StopIteration:
            if is_target:
                raise make_no_solution_error(
                    args.clause_continuation,
                    args.clause_continuation_parameter,
                ) from None
            solution = tuple(retained["solution"])
            current_witness = tuple(retained["witness"])
            console.print_warning(
                "clause continuation produced no witness "
                f"(max clauses={max_clause}); continuing",
                flush=True,
            )
            continue
        except RuntimeError:
            if not is_target:
                raise
            if not args.solution.exists() or args.solution.stat().st_size == 0:
                raise
            with open(args.solution) as stream:
                solution = [line.rstrip() for line in stream if line.rstrip()]
            current_witness = read_structural_witness(args.witness)
            if not solution or not current_witness:
                raise
            console.print_debug(
                "selecting intermediate solution "
                "(reason=final model parsing failed, "
                "certification=partial/non-certified)",
                flush=True,
            )

        final_objective = (
            len(set(solution) & important_nodes_in_domain),
            len(solution),
        )
        if final_objective < retained["objective"]:
            solution = tuple(retained["solution"])
            current_witness = tuple(retained["witness"])
            current_domain = frozenset(retained["domain"])
        else:
            store_model(
                complete_domain,
                solution,
                current_witness,
                force=True,
            )
            current_domain = complete_domain
        write_structural_witness(current_witness, args.witness)
        write_node_solution(solution, args.solution)

    if not solution:
        raise make_no_solution_error(
            args.clause_continuation,
            args.clause_continuation_parameter,
        )

    print_node_solution(
        solution,
        nodes_in_data,
        nodes_in_domain,
        flush=True,
    )

elif args.action == "filter-consts":
    console.print_task("maximizing strong constants")

    bo.maximize_strong_constants()
    if args.minimize_self_loops:
        bo.custom(
            "edge(A,A) :- clause(A,_,A,_). " "#minimize { 1@10000,A: edge(A,A) }."
        )

    important_nodes = set(read_gene_list(args.important_nodes))
    important_nodes_in_domain = important_nodes & set(bo.domain.nodes)
    for node in important_nodes_in_domain:
        bo.custom(f"important_node({clingo_encode(node)}).")

    if important_nodes_in_domain:
        bo.custom(
            "#maximize { 1@1,N: important_node(N), node(N), "
            "not strong_constant(N) }."
        )

    def intermediate_solution(model):
        nodes, witness = model
        write_structural_witness(witness, args.witness)
        write_node_solution(nodes, args.solution)

    clingo_opt_strategy = "usc"
    ptqdm.score_formatter = make_filter_consts_score_formatter(
        node_total=len(bo.domain.nodes),
        important_total=len(important_nodes_in_domain),
    )
    ptqdm.initial_postfix = {
        "total": _format_progress_ratio(0, len(bo.domain.nodes)),
    }
    if important_nodes_in_domain:
        ptqdm.initial_postfix = {
            "important": _format_progress_ratio(
                0,
                len(important_nodes_in_domain),
            ),
            **ptqdm.initial_postfix,
        }
    view = bonesis.NonStrongConstantNodesView(
        bo,
        mode=args.clingo_opt_mode,
        extra=structural_witness,
        intermediate_model_cb=intermediate_solution,
        clingo_opt_strategy=clingo_opt_strategy,
        progress=ptqdm,
        **get_filter_clingo_settings(
            args.clingo_opt_mode,
            clingo_opt_strategy,
            args.clingo_configuration,
            "--opt-usc-shrink=inv",
            clingo_parallel_option,
        ),
    )
    view.standalone(output_filename=args.asp)

    nodes_in_data, nodes_in_domain, domain_edges = get_node_sets(bo)
    print_node_reference(nodes_in_data, nodes_in_domain, domain_edges)
    print_solver_options(
        args.clingo_opt_mode,
        clingo_opt_strategy,
        args.max_clauses,
        canonical,
        configuration=args.clingo_configuration or "auto",
        jobs=args.jobs,
    )
    console.print_options("clause continuation: none")
    console.print_options("domain continuation: none")
    console.print_warning("this may take some time.")
    deadline = SolverDeadline(args.timeout)
    try:
        solution, witness = next_solution(view, deadline)
    except SolverTimeout:
        exit_solver_timeout(args.timeout_status_file)

    write_structural_witness(witness, args.witness)
    write_node_solution(solution, args.solution)

    if important_nodes_in_domain:
        console.print_result(
            "important nodes: "
            f"kept={len(set(solution) & important_nodes_in_domain)}/"
            f"{len(important_nodes_in_domain)}"
        )
    print_node_solution(solution, nodes_in_data, nodes_in_domain)
