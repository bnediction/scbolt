from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import clingo

STRUCTURAL_ATOM_ARITIES = {
    "node": 1,
    "clause": 4,
    "constant": 2,
}


def structural_witness(atoms: Iterable[clingo.Symbol]) -> tuple[str, ...]:
    """Extract the Boolean-network structure needed for a solver warm start."""

    return tuple(
        sorted(
            str(atom)
            for atom in atoms
            if STRUCTURAL_ATOM_ARITIES.get(atom.name) == len(atom.arguments)
        )
    )


def read_structural_witness(file: Path | None) -> tuple[str, ...]:
    """Read and validate a structural witness when one is available."""

    if file is None or not file.is_file():
        return ()

    witness = []
    with open(file) as stream:
        for line_number, line in enumerate(stream, start=1):
            expression = line.strip().removesuffix(".")
            if not expression:
                continue
            try:
                atom = clingo.parse_term(expression)
            except RuntimeError as error:
                raise ValueError(
                    f"invalid structural witness at {file}:{line_number}"
                ) from error
            if STRUCTURAL_ATOM_ARITIES.get(atom.name) != len(atom.arguments):
                raise ValueError(
                    "unsupported structural witness atom at "
                    f"{file}:{line_number}: {atom}"
                )
            witness.append(str(atom))
    return tuple(sorted(set(witness)))


def structural_witness_clause_bound(witness: Iterable[str]) -> int:
    """Return the smallest clause bound compatible with a structural witness."""

    bound = 1
    for expression in witness:
        atom = clingo.parse_term(expression)
        if atom.name != "clause":
            continue

        clause_id = atom.arguments[1]
        if clause_id.type != clingo.SymbolType.Number:
            raise ValueError(f"invalid clause identifier in witness atom: {atom}")
        bound = max(bound, clause_id.number)

    return bound


def structural_witness_nodes(witness: Iterable[str]) -> tuple[str, ...]:
    """Extract selected node names from a serialized structural witness."""

    nodes = []
    for expression in witness:
        atom = clingo.parse_term(expression)
        if atom.name == "node" and len(atom.arguments) == 1:
            node = atom.arguments[0]
            nodes.append(
                node.string
                if node.type == clingo.SymbolType.String
                else str(node)
            )
    return tuple(sorted(set(nodes)))


def canonicalize_structural_witness(
    witness: Iterable[str],
) -> tuple[str, ...]:
    """Convert a structural witness to BoNesis canonical clause ordering."""

    nodes = set()
    constants = set()
    clauses = defaultdict(lambda: defaultdict(set))

    for expression in witness:
        atom = clingo.parse_term(expression)
        if atom.name == "node":
            nodes.add(str(atom))
            continue
        if atom.name == "constant":
            constants.add(str(atom))
            continue
        if atom.name != "clause":
            continue

        target, clause_id, regulator, sign = atom.arguments
        if clause_id.type != clingo.SymbolType.Number:
            raise ValueError(f"invalid clause identifier in witness atom: {atom}")
        clauses[str(target)][clause_id.number].add((str(regulator), str(sign)))

    canonical_clauses = []
    for target, indexed_clauses in sorted(clauses.items()):
        unique_clauses = {
            frozenset(clause) for clause in indexed_clauses.values()
        }
        minimal_clauses = {
            clause
            for clause in unique_clauses
            if not any(other < clause for other in unique_clauses)
        }
        ordered_clauses = sorted(
            minimal_clauses,
            key=lambda clause: (
                len(clause),
                tuple(sorted(regulator for regulator, _ in clause)),
                tuple(sorted(clause)),
            ),
        )

        for clause_id, clause in enumerate(ordered_clauses, start=1):
            for regulator, sign in sorted(clause):
                canonical_clauses.append(
                    f"clause({target},{clause_id},{regulator},{sign})"
                )

    return tuple(
        sorted(nodes)
        + canonical_clauses
        + sorted(constants)
    )


def apply_structural_witness_heuristics(bo, witness: Iterable[str]) -> None:
    """Prefer a structural witness without constraining admissible solutions."""

    witness = tuple(witness)
    if not witness:
        return

    # BoNesis appends a final dot to custom lines. The trailing comment keeps
    # that dot outside the Clingo heuristic directive.
    for expression in witness:
        atom = clingo.parse_term(expression)
        if atom.name in {"clause", "constant"}:
            bo.custom(f"#heuristic {atom}. [1000@100,true] %")
    bo.custom(
        "#heuristic clause(N,C,L,S) : in(L,N,S), maxC(N,M), C=1..M. "
        "[1@10,false] %"
    )
