"""Deterministic candidate scheduling for domain continuation."""

from __future__ import annotations

import random
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from math import ceil
from typing import Literal

DomainOutcome = Literal["sat", "unsat", "unknown", "cancelled"]
DomainUnknownReason = Literal["capacity"]
DomainPhase = Literal[
    "acquisition",
    "expansion",
    "refresh",
    "completion",
    "refinement",
]
DomainLeaderUpdate = Literal["improved", "joined", "unchanged"]

_DOMAIN_TERMINAL_STEP_FRACTION = 0.01
_DOMAIN_TERMINAL_STEP_MINIMUM = 3
_DOMAIN_TERMINAL_STEP_MAXIMUM = 10
_DOMAIN_FRONTIER_GRACE_DIVISOR = 2.5
_SOLVER_RANDOM_FREQUENCY = "0.01"


@dataclass(frozen=True)
class DomainCandidate:
    """One reproducible domain and solver profile within a continuation wave."""

    index: int
    nodes: frozenset[str]
    solver_options: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainCandidateResult:
    """Solver outcome retained for one candidate domain."""

    candidate: DomainCandidate
    outcome: DomainOutcome
    solution: tuple[str, ...] = ()
    witness: tuple[str, ...] = ()
    unknown_reason: DomainUnknownReason | None = None
    optimum_certified: bool = False


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


@dataclass
class DomainPortfolioLaunchState:
    """Coordinate a grounded memory probe and staggered worker launches."""

    probe_required: bool
    probe_seconds: float
    launch_interval_seconds: float
    probe_complete: bool = field(init=False)
    _probe_started_at: float | None = field(default=None, init=False)
    _last_launch_at: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.probe_seconds < 0:
            raise ValueError("memory probe duration cannot be negative")
        if self.launch_interval_seconds < 0:
            raise ValueError("candidate launch interval cannot be negative")
        self.probe_complete = not self.probe_required

    def mark_submitted(self, now: float) -> None:
        """Record one worker submission."""

        self._last_launch_at = now

    def mark_probe_candidate_ready(self, now: float) -> None:
        """Start the probe once its first worker has completed grounding."""

        if self.probe_required and self._probe_started_at is None:
            self._probe_started_at = now

    def update_probe(self, now: float, *, has_pending: bool) -> None:
        """Complete the probe after its observation window or worker exit."""

        if self.probe_complete or self._probe_started_at is None:
            return
        if (
            not has_pending
            or now - self._probe_started_at >= self.probe_seconds
        ):
            self.probe_complete = True

    def ready_for_launch(self, now: float, *, has_pending: bool) -> bool:
        """Report whether another worker may be submitted now."""

        if not self.probe_complete:
            # Retry a sole probe worker if its predecessor failed before
            # completing grounding.
            return not has_pending and self._probe_started_at is None
        if self._last_launch_at is None:
            return True
        return now - self._last_launch_at >= self.launch_interval_seconds


@dataclass
class DomainMemoryEstimator:
    """Retain a conservative per-worker estimate across domain waves."""

    _candidate_cost_floor: float = field(default=0.0, init=False)
    _cost_per_problem_unit: float = field(default=0.0, init=False)

    def observe(
        self,
        candidate_cost: float,
        *,
        domain_size: int,
        max_clause: int,
    ) -> None:
        """Retain a measured candidate cost without lowering prior bounds."""

        self._validate_problem(domain_size, max_clause)
        if candidate_cost <= 0:
            return
        self._candidate_cost_floor = max(
            self._candidate_cost_floor,
            candidate_cost,
        )
        self._cost_per_problem_unit = max(
            self._cost_per_problem_unit,
            candidate_cost / (domain_size * max_clause),
        )

    def estimate(self, *, domain_size: int, max_clause: int) -> float | None:
        """Estimate one worker while scaling for domain and clause growth."""

        self._validate_problem(domain_size, max_clause)
        if self._candidate_cost_floor <= 0:
            return None
        return max(
            self._candidate_cost_floor,
            self._cost_per_problem_unit * domain_size * max_clause,
        )

    @staticmethod
    def _validate_problem(domain_size: int, max_clause: int) -> None:
        if domain_size < 1:
            raise ValueError("candidate domain size must be positive")
        if max_clause < 1:
            raise ValueError("maximum clause count must be positive")


def solution_objective(
    solution: Iterable[str],
    important_nodes: Collection[str],
) -> tuple[int, int]:
    """Return the lexicographic node-selection objective of a solution."""

    nodes = set(solution)
    return len(nodes & set(important_nodes)), len(nodes)


def domain_frontier_grace_seconds(patience_seconds: float) -> float:
    """Return the grace granted to a newly competitive domain worker."""

    if patience_seconds < 0:
        raise ValueError("domain wave patience cannot be negative")
    return patience_seconds / _DOMAIN_FRONTIER_GRACE_DIVISOR


def clause_continuation_bounds(
    max_clauses: int,
    lower_bound: int = 1,
) -> tuple[int, ...]:
    """Return increasing clause bounds compatible with an initial witness."""

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


def solution_reaches_domain_ceiling(
    solution: Iterable[str],
    domain_nodes: Collection[str],
    important_nodes: Collection[str],
) -> bool:
    """Report whether a solution reaches the domain objective upper bound."""

    return solution_objective(
        solution,
        important_nodes,
    ) == solution_objective(domain_nodes, important_nodes)


def portfolio_objective_ceiling(
    candidates: Collection[DomainCandidate],
    important_nodes: Collection[str],
) -> tuple[int, int]:
    """Return the best objective upper bound among candidate domains."""

    if not candidates:
        raise ValueError("domain portfolio cannot be empty")
    return max(
        solution_objective(candidate.nodes, important_nodes)
        for candidate in candidates
    )


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


def stalled_domain_solver_settings(
    mode: str,
    strategy: str,
) -> tuple[str, str] | None:
    """Select a complementary solver after domain expansion stalls."""

    if mode != "ignore" and strategy != "bb,lin":
        return "opt", "bb,lin"
    return None


def terminal_refinement_solver_settings(
    mode: str,
    strategy: str,
    *,
    optimum_certified: bool,
) -> tuple[str, str] | None:
    """Select the complete-domain refinement portfolio strategy."""

    if not optimum_certified and mode != "ignore" and strategy != "bb,lin":
        return "opt", "bb,lin"
    return None


def solver_result_certifies_optimum(
    mode: str,
    *,
    interrupted: bool,
) -> bool:
    """Report whether a completed candidate proves its optimum."""

    return mode in {"opt", "optN"} and not interrupted


def minimum_domain_gain(expansion_size: int, minimum_yield: float) -> int:
    """Return the retained-node gain required to accept an expansion."""

    if expansion_size < 0:
        raise ValueError("domain expansion size cannot be negative")
    if not 0 <= minimum_yield < 1:
        raise ValueError("minimum domain yield must be at least 0 and below 1")
    if expansion_size == 0 or minimum_yield == 0:
        return 0
    return max(1, ceil(expansion_size * minimum_yield))


def candidate_fits_memory_budget(
    memory_limit: int | None,
    current_rss: int | None,
    candidate_cost: float | None,
    *,
    cost_factor: float,
    reserved_candidates: int = 0,
) -> bool:
    """Report whether one additional candidate fits the current RSS budget."""

    if cost_factor < 1:
        raise ValueError("candidate memory cost factor must be at least one")
    if reserved_candidates < 0:
        raise ValueError("reserved candidate count cannot be negative")
    if (
        memory_limit is None
        or current_rss is None
        or candidate_cost is None
        or candidate_cost <= 0
    ):
        return True
    reserved_cost = cost_factor * candidate_cost * (reserved_candidates + 1)
    return current_rss + reserved_cost <= memory_limit


def initial_domain_size(required_size: int, complete_size: int) -> int:
    """Return the midpoint used by the first acquisition wave."""

    _validate_domain_sizes(required_size, complete_size)
    return required_size + ceil((complete_size - required_size) / 2)


def expansion_domain_size(current_size: int, complete_size: int) -> int:
    """Return the next midpoint, coalescing small terminal expansions."""

    _validate_domain_sizes(current_size, complete_size)
    remaining = complete_size - current_size
    expansion = ceil(remaining / 2)
    terminal_step = max(
        _DOMAIN_TERMINAL_STEP_MINIMUM,
        min(
            _DOMAIN_TERMINAL_STEP_MAXIMUM,
            ceil(complete_size * _DOMAIN_TERMINAL_STEP_FRACTION),
        ),
    )
    if expansion <= terminal_step:
        return complete_size
    return current_size + expansion


def reduced_domain_expansion_size(expansion_size: int) -> int | None:
    """Halve an unresolved expansion, or report its minimum boundary."""

    if expansion_size < 1:
        raise ValueError("domain expansion size must be positive")
    if expansion_size == 1:
        return None
    return max(1, expansion_size // 2)


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
    """Build equally sized workers, preferring distinct candidate domains."""

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
        return _fill_candidate_workers(
            (DomainCandidate(1, nodes),),
            jobs=jobs,
            seed=seed,
            clause_bound=clause_bound,
            wave=wave,
        )

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

    return _fill_candidate_workers(
        candidates,
        jobs=jobs,
        seed=seed,
        clause_bound=clause_bound,
        wave=wave,
    )


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
            result.optimum_certified,
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


def _fill_candidate_workers(
    candidates: Sequence[DomainCandidate],
    *,
    jobs: int,
    seed: int,
    clause_bound: int,
    wave: int,
) -> tuple[DomainCandidate, ...]:
    """Fill unavailable domain slots with deterministic solver profiles."""

    workers = list(candidates)
    if not workers or len(workers) >= jobs:
        return tuple(workers)

    distinct_candidates = tuple(workers)
    generator = random.Random(f"{seed}:{clause_bound}:{wave}:solver")
    solver_seeds = set()
    duplicate_index = 0
    while len(workers) < jobs:
        source = distinct_candidates[duplicate_index % len(distinct_candidates)]
        solver_seed = generator.getrandbits(31)
        while solver_seed in solver_seeds:
            solver_seed = generator.getrandbits(31)
        solver_seeds.add(solver_seed)
        workers.append(
            DomainCandidate(
                index=len(workers) + 1,
                nodes=source.nodes,
                solver_options=(
                    f"--seed={solver_seed}",
                    "--sign-def=rnd",
                    f"--rand-freq={_SOLVER_RANDOM_FREQUENCY}",
                ),
            )
        )
        duplicate_index += 1

    return tuple(workers)
