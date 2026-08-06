"""Shared primitives for BoNesis component-selection stages."""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from contextlib import ExitStack
from numbers import Number
from pathlib import Path
from threading import Event, Thread
from typing import Any

import bonesis
from tqdm import tqdm

from scbolt import console
from scbolt.runtime import SolverCapacityError, SolverPatience, format_duration

from ._witness import (
    apply_structural_witness_heuristics,
    write_structural_witness,
)

DISABLE_TQDM = os.getenv("TQDM_DISABLE", "0") == "1"
TQDM_TO_TTY = os.getenv("TQDM_TO_TTY", "0") == "1"


class ptqdm(tqdm):
    """Transient tqdm variant with stable structured score formatting."""

    score_formatter: Callable[[Sequence[int]], Mapping[str, str]] | None = None
    initial_postfix: Mapping[str, str] | None = None

    def __init__(self, *args, **kwargs):
        kwargs["leave"] = False
        kwargs.setdefault("dynamic_ncols", True)

        self._tqdm_file_context = ExitStack()
        self._tqdm_file = None
        if TQDM_TO_TTY and "file" not in kwargs:
            try:
                self._tqdm_file = self._tqdm_file_context.enter_context(
                    console.open_terminal_stream()
                )
                kwargs.setdefault("file", self._tqdm_file)
            except OSError:
                pass
        else:
            kwargs.setdefault("file", sys.stdout)

        if type(self).initial_postfix is not None:
            kwargs.setdefault("postfix", type(self).initial_postfix)
        kwargs.setdefault("disable", DISABLE_TQDM)
        super().__init__(*args, **kwargs)

    def close(self):
        super().close()
        if self._tqdm_file is not None:
            self._tqdm_file_context.close()
            self._tqdm_file = None

    def set_postfix(self, ordered_dict=None, refresh=True, **kwargs):
        score_formatter = type(self).score_formatter
        if (
            score_formatter is not None
            and ordered_dict is not None
            and "score" in ordered_dict
        ):
            ordered_dict = score_formatter(ordered_dict["score"])

        postfix = OrderedDict([] if ordered_dict is None else ordered_dict)
        for key in sorted(kwargs):
            postfix[key] = kwargs[key]
        for key, value in postfix.items():
            if isinstance(value, Number):
                postfix[key] = self.format_num(value)
            elif not isinstance(value, str):
                postfix[key] = str(value)

        # tqdm strips string values, which removes deliberate numeric padding.
        self.postfix = ", ".join(f"{key}={value}" for key, value in postfix.items())
        if refresh:
            self.refresh()


class BooleanNetworkProgress(ptqdm):
    """Render BoNesis network enumeration as a regular scBOLT progress bar."""

    _refresh_interval = 1.0

    def __init__(
        self,
        *args,
        label: str,
        limit: int | None,
        initial: int = 0,
        started_at: float | None = None,
        supervisor: Any | None = None,
        **kwargs,
    ) -> None:
        self._label = label
        self._supervisor = supervisor
        self._refresh_stop = Event()
        self._refresh_thread: Thread | None = None
        requested_stream = kwargs.get("file")
        kwargs.pop("bar_format", None)
        kwargs["desc"] = label
        kwargs["dynamic_ncols"] = False
        kwargs["initial"] = initial
        kwargs["ncols"] = 100
        kwargs["smoothing"] = 0
        kwargs["total"] = limit or None
        kwargs["unit"] = "network"
        if not limit:
            kwargs["bar_format"] = (
                "{desc}: {n_fmt} networks [{elapsed}, {rate_fmt}]"
            )
        super().__init__(*args, **kwargs)
        if started_at is not None:
            self.start_t = started_at
            self.last_print_t = started_at
            # The displayed count includes recovered networks, so rate and ETA
            # must use that same cumulative count rather than only this cycle.
            self.initial = 0
        progress_stream = requested_stream or self._tqdm_file or sys.stdout
        if not self.disable and progress_stream.isatty():
            if self._supervisor is not None:
                self._supervisor.attach_progress(self)
            else:
                self._refresh_thread = Thread(
                    target=self._refresh_periodically,
                    name="scbolt-network-progress",
                    daemon=True,
                )
                self._refresh_thread.start()

    def close(self) -> None:
        if self._supervisor is not None:
            self._supervisor.detach_progress(self)
        self._refresh_stop.set()
        if self._refresh_thread is not None:
            self._refresh_thread.join()
            self._refresh_thread = None
        super().close()

    def set_description_str(self, _desc=None, refresh=True) -> None:
        """Keep the stable scBOLT label when BoNesis updates its counter."""

        super().set_description_str(self._label, refresh=refresh)

    def _refresh_periodically(self) -> None:
        """Refresh elapsed time and average rate between network solutions."""

        while not self._refresh_stop.wait(self._refresh_interval):
            self.refresh()


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
            observed = filter_nodes_objective(
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
                key: value for key, value in ordered_dict.items() if key != "score"
            }
            ordered_dict.update(self._inherited_score_formatter(score))
        super().set_postfix(ordered_dict, refresh=refresh, **kwargs)


def filter_nodes_objective(
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
        important, total = filter_nodes_objective(
            score,
            has_important_nodes=bool(important_total),
        )
        fields = {}

        if important_total:
            fields["important"] = format_progress_ratio(
                important,
                important_total,
            )
            fields["total"] = format_progress_ratio(total, node_total)
        elif len(score):
            fields["total"] = format_progress_ratio(total, node_total)

        return fields or {"score": str(list(score))}

    return format_score


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
        fields = {"total": format_progress_ratio(kept_nodes, node_total)}
        if important_total and len(values) >= 2:
            fields = {
                "important": format_progress_ratio(
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
    for name, value in bo.aspmodel.constants.items():
        stage.set_constant(name, value)
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
    inherited_score = (important, total) if has_important_nodes else (total,)
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


def print_node_solution(solution, nodes_in_data, nodes_in_domain, **kwargs):
    """Print node-selection coverage against data and domain nodes."""

    solution = set(solution)
    console.print_result(f"solution: nodes={len(solution)}", **kwargs)
    console.print_result(
        _format_node_coverage(
            "data",
            len(nodes_in_data & solution),
            len(nodes_in_data),
        ),
        **kwargs,
    )
    console.print_result(
        _format_node_coverage(
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
        stream.writelines(f"{line}\n" for line in lines)
    os.replace(temporary, file)


def write_node_solution(nodes: Iterable[str], file: Path) -> None:
    """Atomically write one selected node per line."""

    write_lines(nodes, file)


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


def make_solver_capacity_error(
    error: SolverCapacityError,
    *,
    domain_continuation: bool,
    clause_continuation_parameter: str | None,
    domain_continuation_available: bool = True,
) -> SolverCapacityError:
    """Add the stage-specific recovery path to a Clasp capacity failure."""

    if domain_continuation:
        suggestion = (
            "the complete regulatory domain still exceeds this limit; "
            "reduce the prior network"
        )
    elif not domain_continuation_available:
        suggestion = "reduce the prior network"
    elif clause_continuation_parameter is not None:
        parameter = clause_continuation_parameter.replace(
            "CLAUSE_CONTINUATION_",
            "DOMAIN_CONTINUATION_",
            1,
        )
        suggestion = (
            f"enable domain continuation with {parameter}=true or reduce "
            "the prior network"
        )
    else:
        suggestion = "enable domain continuation or reduce the prior network"

    return SolverCapacityError(f"{error}; {suggestion}")


def print_clause_bound_patience_warning(
    max_clause: int,
    objective: tuple[int, int],
    *,
    node_total: int,
    important_total: int,
    patience: float,
) -> None:
    """Report the best objective retained at an exhausted clause bound."""

    solution_summary = _format_solution_objective(
        objective,
        node_total=node_total,
        important_total=important_total,
    )
    console.print_warning(
        "no objective improvement within the clause-bound patience "
        f"[max clauses={max_clause}, "
        f"time={format_duration(patience)}]: "
        f"{solution_summary}",
        flush=True,
    )


def store_retained_model(
    retained: dict[str, Any],
    domain: Iterable[str],
    nodes: Iterable[str],
    witness: Iterable[str],
    *,
    important_nodes: Collection[str],
    witness_file: Path,
    solution_file: Path,
    force: bool = False,
) -> bool:
    """Persist a first or improved node-selection model."""

    domain = frozenset(domain)
    nodes = tuple(sorted(nodes))
    witness = tuple(witness)
    objective = len(set(nodes) & set(important_nodes)), len(nodes)
    improved = objective > retained["objective"]
    if not force and not improved:
        return False

    retained["domain"] = domain
    retained["solution"] = nodes
    retained["witness"] = witness
    retained["objective"] = objective
    write_structural_witness(witness, witness_file)
    write_node_solution(nodes, solution_file)
    return improved


def retain_intermediate_node_solution(
    model,
    *,
    stage_best: list,
    retain_model: Callable,
    complete_domain: Collection[str],
    stage_patience: SolverPatience,
) -> None:
    """Retain an intermediate node solution and reset patience if improved."""

    stage_best[0] = model
    nodes, witness = model
    if retain_model(complete_domain, nodes, witness):
        stage_patience.reset()


def write_intermediate_solution(
    model,
    *,
    witness_file: Path,
    solution_file: Path,
) -> None:
    """Persist an intermediate strong-constant solution."""

    nodes, witness = model
    write_structural_witness(witness, witness_file)
    write_node_solution(nodes, solution_file)


def format_progress_ratio(value: int, total: int) -> str:
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


def _format_node_coverage(name, kept, total):
    """Format retained and removed node counts."""

    removed = total - kept
    pct = 0 if total == 0 else 100 * kept / total
    return f"{name}: kept={kept}/{total} ({pct:.1f}%), removed={removed}"
