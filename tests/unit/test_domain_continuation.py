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
    expansion_domain_size,
    initial_domain_size,
    outcome_counts,
    select_best_candidate,
    solution_objective,
)

complete = {f"g{i}" for i in range(20)}
current = {"g0", "g1", "g2"}

assert initial_domain_size(3, 20) == 12
assert expansion_domain_size(12, 20) == 16
assert bounded_midpoint(3, 20) == 12

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

print("domain continuation tests passed")
