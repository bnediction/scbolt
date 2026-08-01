"""Boolean inference support for scBOLT."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SPECIFICATION_SECTIONS = (
    "constraints",
    "important-nodes",
    "mandatory-nodes",
    "forbidden-nodes",
)


def should_forward_previous_solution(
    new_constraints: bool,
    initial_witness: Iterable[str],
) -> bool:
    """Return whether this stage can forward its predecessor unchanged."""

    return not new_constraints and not tuple(initial_witness)


def write_influence_graph(
    boolean_network: Any,
    outdir: str | Path,
    programs: Sequence[str] = ("dot",),
    remove_isolated_nodes: bool = False,
) -> None:
    """Write a Boolean network influence graph using Graphviz."""

    influence_graph = boolean_network.to_influence_graph()

    if remove_isolated_nodes:
        isolated_nodes = [
            node for node, degree in influence_graph.degree if degree == 0
        ]
        influence_graph.remove_nodes_from(isolated_nodes)

    graph = influence_graph.to_pydot()
    outdir = Path(outdir)
    for program in programs:
        graph.write(
            outdir / f"ig.{program}",
            prog=program,
            format="raw",
        )


def normalize_model_specification(value: Any) -> dict[str, list[str]]:
    """Validate and normalize a Boolean model specification mapping."""

    if not isinstance(value, Mapping):
        raise TypeError("model specification must be a YAML mapping")

    unknown_sections = sorted(set(value) - set(SPECIFICATION_SECTIONS))
    if unknown_sections:
        raise ValueError(
            "unknown model specification section(s): "
            + ", ".join(unknown_sections)
        )
    if "constraints" not in value:
        raise ValueError("missing model specification section: constraints")

    specification = {}
    for key in SPECIFICATION_SECTIONS:
        values = value.get(key)
        if values is None:
            specification[key] = []
            continue
        if not isinstance(values, list):
            raise TypeError(
                f"model specification section '{key}' must be a list"
            )
        if not all(isinstance(item, str) for item in values):
            raise TypeError(
                f"model specification section '{key}' must contain only strings"
            )
        specification[key] = values

    return specification
