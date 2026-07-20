"""Deterministic candidate scheduling for domain continuation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import ceil
from typing import Collection, Iterable, Literal, Sequence

DomainOutcome = Literal["sat", "unsat", "unknown", "cancelled"]


@dataclass(frozen=True)
class DomainCandidate:
    """One reproducible candidate domain within a continuation wave."""

    index: int
    nodes: frozenset[str]


@dataclass(frozen=True)
class DomainCandidateResult:
    """Solver outcome retained for one candidate domain."""

    candidate: DomainCandidate
    outcome: DomainOutcome
    solution: tuple[str, ...] = ()
    witness: tuple[str, ...] = ()


@dataclass
class DomainWaveLeader:
    """Track the candidate holding the best objective within one wave."""

    candidate_index: int | None = None
    objective: tuple[int, int] | None = None

    def update(
        self,
        candidate_index: int,
        solution: Iterable[str],
        important_nodes: Collection[str],
    ) -> bool:
        """Adopt a first or strictly better wave objective."""

        objective = solution_objective(solution, important_nodes)
        if self.objective is not None and objective <= self.objective:
            return False

        self.candidate_index = candidate_index
        self.objective = objective
        return True


def solution_objective(
    solution: Iterable[str],
    important_nodes: Collection[str],
) -> tuple[int, int]:
    """Return the lexicographic node-selection objective of a solution."""

    nodes = set(solution)
    return len(nodes & set(important_nodes)), len(nodes)


def initial_domain_size(required_size: int, complete_size: int) -> int:
    """Return the midpoint used by the first acquisition wave."""

    _validate_domain_sizes(required_size, complete_size)
    return required_size + ceil((complete_size - required_size) / 2)


def expansion_domain_size(current_size: int, complete_size: int) -> int:
    """Return the next midpoint between a retained domain and the full one."""

    _validate_domain_sizes(current_size, complete_size)
    return current_size + ceil((complete_size - current_size) / 2)


def bounded_midpoint(lower: int, upper: int) -> int:
    """Return an interior midpoint, preferring the larger half."""

    if lower > upper:
        raise ValueError("lower domain bound cannot exceed upper domain bound")
    if lower == upper:
        return lower
    return lower + ceil((upper - lower) / 2)


def build_candidate_wave(
    complete_nodes: Collection[str],
    current_nodes: Collection[str],
    *,
    target_size: int,
    jobs: int,
    seed: int,
    clause_bound: int,
    wave: int,
) -> tuple[DomainCandidate, ...]:
    """Build distinct, equally sized supersets of the current domain."""

    complete = frozenset(complete_nodes)
    current = frozenset(current_nodes)
    if not current <= complete:
        raise ValueError("current domain must be a subset of the complete domain")
    if not len(current) <= target_size <= len(complete):
        raise ValueError(
            "target domain size must be between current and complete sizes"
        )
    if jobs < 1:
        raise ValueError("domain continuation jobs must be positive")

    addition_count = target_size - len(current)
    available = sorted(complete - current)
    if addition_count == 0 or addition_count == len(available):
        return (DomainCandidate(1, frozenset(complete if addition_count else current)),)

    candidates = []
    seen = set()
    attempt = 0
    max_attempts = max(32, jobs * 64)
    while len(candidates) < jobs and attempt < max_attempts:
        candidate_index = len(candidates) + 1
        branch_seed = (
            f"{seed}:{clause_bound}:{wave}:{candidate_index}:{attempt}"
        )
        ordered = available.copy()
        random.Random(branch_seed).shuffle(ordered)
        nodes = frozenset((*current, *ordered[:addition_count]))
        attempt += 1
        if nodes in seen:
            continue
        seen.add(nodes)
        candidates.append(DomainCandidate(candidate_index, nodes))

    return tuple(candidates)


def select_best_candidate(
    results: Iterable[DomainCandidateResult],
    important_nodes: Collection[str],
) -> DomainCandidateResult | None:
    """Select the best satisfiable candidate with deterministic tie-breaking."""

    important = set(important_nodes)
    satisfiable = [result for result in results if result.outcome == "sat"]
    if not satisfiable:
        return None

    return max(
        satisfiable,
        key=lambda result: (
            *solution_objective(result.solution, important),
            -result.candidate.index,
        ),
    )


def outcome_counts(
    results: Sequence[DomainCandidateResult],
) -> dict[DomainOutcome, int]:
    """Count candidate outcomes in a stable display order."""

    return {
        outcome: sum(result.outcome == outcome for result in results)
        for outcome in ("sat", "unsat", "unknown", "cancelled")
    }


def _validate_domain_sizes(current_size: int, complete_size: int) -> None:
    if current_size < 0:
        raise ValueError("domain size cannot be negative")
    if current_size > complete_size:
        raise ValueError("current domain cannot exceed the complete domain")
