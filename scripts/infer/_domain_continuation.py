"""Deterministic candidate scheduling for domain continuation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import combinations
from math import ceil
from typing import Collection, Iterable, Literal, Sequence

DomainOutcome = Literal["sat", "unsat", "unknown", "cancelled"]
DomainUnknownReason = Literal["capacity"]
DomainPhase = Literal["acquisition", "expansion", "refresh"]
DomainLeaderUpdate = Literal["improved", "joined", "unchanged"]


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
    unknown_reason: DomainUnknownReason | None = None


@dataclass
class DomainWaveLeader:
    """Track the best objective and candidates that reached its frontier."""

    candidate_index: int | None = None
    objective: tuple[int, int] | None = None
    frontier_candidates: set[int] = field(default_factory=set)

    def update(
        self,
        candidate_index: int,
        solution: Iterable[str],
        important_nodes: Collection[str],
    ) -> DomainLeaderUpdate:
        """Classify how a candidate changes the shared objective frontier."""

        objective = solution_objective(solution, important_nodes)
        if self.objective is None or objective > self.objective:
            self.candidate_index = candidate_index
            self.objective = objective
            self.frontier_candidates = {candidate_index}
            return "improved"
        if objective < self.objective:
            return "unchanged"
        if candidate_index in self.frontier_candidates:
            return "unchanged"

        self.frontier_candidates.add(candidate_index)
        return "joined"


def solution_objective(
    solution: Iterable[str],
    important_nodes: Collection[str],
) -> tuple[int, int]:
    """Return the lexicographic node-selection objective of a solution."""

    nodes = set(solution)
    return len(nodes & set(important_nodes)), len(nodes)


def continuation_base_domain(
    solution_nodes: Iterable[str],
    required_nodes: Collection[str],
    complete_nodes: Collection[str],
) -> frozenset[str]:
    """Build the domain retained when continuing at another clause bound."""

    complete = frozenset(complete_nodes)
    base = frozenset(solution_nodes) | frozenset(required_nodes)
    if not base <= complete:
        raise ValueError("continuation domain exceeds the complete domain")
    return base


def domain_expansion_gains(
    previous_solution: Iterable[str],
    current_solution: Iterable[str],
    important_nodes: Collection[str],
) -> tuple[int, int]:
    """Return cumulative important and total gains for one expansion."""

    previous = set(previous_solution)
    current = set(current_solution)
    important = set(important_nodes)
    return (
        max(0, len(current & important) - len(previous & important)),
        max(0, len(current) - len(previous)),
    )


def domain_wave_solver_settings(
    phase: DomainPhase,
    mode: str,
    strategy: str,
) -> tuple[str, str]:
    """Use linear branch-and-bound only while refreshing a domain."""

    if phase == "refresh":
        return "opt", "bb,lin"
    return mode, strategy


def minimum_domain_gain(expansion_size: int, minimum_yield: float) -> int:
    """Return the retained-node gain required to accept an expansion."""

    if expansion_size < 0:
        raise ValueError("domain expansion size cannot be negative")
    if not 0 <= minimum_yield < 1:
        raise ValueError("minimum domain yield must be at least 0 and below 1")
    if expansion_size == 0 or minimum_yield == 0:
        return 0
    return max(1, ceil(expansion_size * minimum_yield))


def memory_limited_portfolio_size(
    memory_limit: int | None,
    memory_baseline: int | None,
    candidate_cost: float | None,
    *,
    jobs: int,
    cost_factor: float,
) -> int:
    """Estimate how many equal-cost candidates fit in the memory budget."""

    if jobs < 1:
        raise ValueError("domain continuation jobs must be positive")
    if cost_factor < 1:
        raise ValueError("candidate memory cost factor must be at least one")
    if (
        memory_limit is None
        or memory_baseline is None
        or candidate_cost is None
        or candidate_cost <= 0
    ):
        return jobs

    candidate_budget = max(0, memory_limit - memory_baseline)
    capacity = int(candidate_budget / (cost_factor * candidate_cost))
    return max(1, min(jobs, capacity))


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
    excluded_domains: Collection[Collection[str]] = (),
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

    excluded = {frozenset(nodes) for nodes in excluded_domains}
    addition_count = target_size - len(current)
    available = sorted(complete - current)
    if addition_count == 0 or addition_count == len(available):
        nodes = frozenset(complete if addition_count else current)
        if nodes in excluded:
            return ()
        return (DomainCandidate(1, nodes),)

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
        if nodes in seen or nodes in excluded:
            continue
        seen.add(nodes)
        candidates.append(DomainCandidate(candidate_index, nodes))

    if len(candidates) < jobs:
        for additions in combinations(available, addition_count):
            nodes = frozenset((*current, *additions))
            if nodes in seen or nodes in excluded:
                continue
            seen.add(nodes)
            candidates.append(DomainCandidate(len(candidates) + 1, nodes))
            if len(candidates) == jobs:
                break

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
