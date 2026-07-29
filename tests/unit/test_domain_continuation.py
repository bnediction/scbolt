#!/usr/bin/env python3

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "infer"))

from _domain_continuation import (  # noqa: E402
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

complete = {f"g{i}" for i in range(20)}
current = {"g0", "g1", "g2"}

assert initial_domain_size(3, 20) == 12
assert expansion_domain_size(12, 20) == 16
assert bounded_midpoint(3, 20) == 12
assert minimum_domain_gain(120, 0.10) == 12
assert minimum_domain_gain(5, 0.99) == 5
assert minimum_domain_gain(5, 0) == 0
assert minimum_domain_gain(120, 0.099) == 12
assert domain_expansion_gains(
    ("g0", "g1"),
    ("g0", "g1", "g2"),
    {"g1", "g2"},
) == (1, 1)

complete_550 = {f"n{i}" for i in range(550)}
selected_500 = {f"n{i}" for i in range(500)}
required = {"n0", "n499"}
clause_base = continuation_base_domain(
    selected_500,
    required,
    complete_550,
)
assert clause_base == selected_500

clause_sizes = [len(clause_base)]
while clause_sizes[-1] < len(complete_550):
    clause_sizes.append(
        expansion_domain_size(clause_sizes[-1], len(complete_550))
    )
assert clause_sizes == [500, 525, 538, 544, 547, 549, 550]

clause_wave = build_candidate_wave(
    complete_550,
    clause_base,
    target_size=clause_sizes[1],
    jobs=4,
    seed=10,
    clause_bound=2,
    wave=1,
)
assert all(selected_500 <= candidate.nodes for candidate in clause_wave)
assert all(len(candidate.nodes) == 525 for candidate in clause_wave)

base_with_unselected_requirement = continuation_base_domain(
    selected_500,
    {"n525"},
    complete_550,
)
assert base_with_unselected_requirement == selected_500 | {"n525"}

# LOCK starts from the complete SEED solution and only expands toward the
# RELAXED domain; it never needs a first-witness acquisition domain.
lock_seed_solution = {f"n{i}" for i in range(500)}
lock_required_nodes = lock_seed_solution | {"n525"}
lock_base = continuation_base_domain(
    lock_seed_solution,
    lock_required_nodes,
    complete_550,
)
assert lock_seed_solution <= lock_base
assert len(lock_base) == 501
assert expansion_domain_size(len(lock_base), len(complete_550)) == 526

try:
    continuation_base_domain({"outside"}, (), complete_550)
except ValueError:
    pass
else:
    raise AssertionError("clause continuation accepted a node outside the domain")

wave = build_candidate_wave(
    complete,
    current,
    target_size=10,
    jobs=4,
    seed=10,
    clause_bound=1,
    wave=1,
)
repeated = build_candidate_wave(
    complete,
    current,
    target_size=10,
    jobs=4,
    seed=10,
    clause_bound=1,
    wave=1,
)

assert wave == repeated
assert len(wave) == 4
assert len({candidate.nodes for candidate in wave}) == 4
assert all(current <= candidate.nodes <= complete for candidate in wave)
assert all(len(candidate.nodes) == 10 for candidate in wave)

refreshed_wave = build_candidate_wave(
    complete,
    current,
    target_size=10,
    jobs=4,
    seed=10,
    clause_bound=1,
    wave=2,
    excluded_domains=[candidate.nodes for candidate in wave],
)
assert len(refreshed_wave) == 4
assert not {
    candidate.nodes for candidate in refreshed_wave
} & {
    candidate.nodes for candidate in wave
}

expansion_base = frozenset({"g0", "g1", "g2"})
expanded_solution = frozenset({"g0", "g1", "g2", "g3"})
refresh_core = expansion_base | expanded_solution
protected_wave = build_candidate_wave(
    complete,
    refresh_core,
    target_size=10,
    jobs=4,
    seed=10,
    clause_bound=1,
    wave=3,
    excluded_domains=[candidate.nodes for candidate in wave],
)
assert all(refresh_core <= candidate.nodes for candidate in protected_wave)
assert all(len(candidate.nodes - refresh_core) == 6 for candidate in protected_wave)

small_complete = {"g0", "g1", "g2", "g3", "g4"}
small_current = {"g0", "g1", "g2"}
small_wave = build_candidate_wave(
    small_complete,
    small_current,
    target_size=4,
    jobs=8,
    seed=10,
    clause_bound=1,
    wave=1,
)
assert len(small_wave) == 2
assert build_candidate_wave(
    small_complete,
    small_current,
    target_size=4,
    jobs=8,
    seed=10,
    clause_bound=1,
    wave=2,
    excluded_domains=[candidate.nodes for candidate in small_wave],
) == ()

next_wave = build_candidate_wave(
    complete,
    wave[0].nodes,
    target_size=15,
    jobs=4,
    seed=10,
    clause_bound=1,
    wave=2,
)
assert all(wave[0].nodes < candidate.nodes for candidate in next_wave)
assert len({candidate.nodes for candidate in next_wave}) == 4

full_wave = build_candidate_wave(
    complete,
    current,
    target_size=len(complete),
    jobs=8,
    seed=10,
    clause_bound=1,
    wave=3,
)
assert full_wave == (DomainCandidate(1, frozenset(complete)),)

results = (
    DomainCandidateResult(wave[0], "sat", ("g0", "g3"), ("node(g0)",)),
    DomainCandidateResult(
        wave[1],
        "sat",
        ("g0", "g1", "g4"),
        ("node(g0)",),
    ),
    DomainCandidateResult(wave[2], "unknown"),
    DomainCandidateResult(wave[3], "unsat"),
)
selected = select_best_candidate(results, {"g0", "g1"})
assert selected == results[1]
assert solution_objective(results[1].solution, {"g0", "g1"}) == (2, 3)
assert outcome_counts(results) == {
    "sat": 2,
    "unsat": 1,
    "unknown": 1,
    "cancelled": 0,
}

capacity_result = DomainCandidateResult(
    wave[2],
    "unknown",
    unknown_reason="capacity",
)
assert capacity_result.unknown_reason == "capacity"

leader = DomainWaveLeader()
assert leader.update(1, ("g0",), {"g0", "g1"})
assert leader.candidate_index == 1
assert leader.objective == (1, 1)
assert not leader.update(2, ("g0",), {"g0", "g1"})
assert not leader.update(2, ("g2", "g3"), {"g0", "g1"})
assert leader.candidate_index == 1
assert leader.update(2, ("g0", "g2"), {"g0", "g1"})
assert leader.candidate_index == 2
assert leader.objective == (1, 2)
assert leader.update(3, ("g0", "g1"), {"g0", "g1"})
assert leader.candidate_index == 3
assert leader.objective == (2, 2)

try:
    build_candidate_wave(
        complete,
        {"missing"},
        target_size=5,
        jobs=1,
        seed=10,
        clause_bound=1,
        wave=1,
    )
except ValueError:
    pass
else:
    raise AssertionError("candidate wave accepted nodes outside the full domain")

for invalid_yield in (-0.01, 1.0):
    try:
        minimum_domain_gain(10, invalid_yield)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid minimum domain yield was accepted")

print("domain continuation tests passed")
