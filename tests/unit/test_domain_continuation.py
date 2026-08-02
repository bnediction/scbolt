import sys
from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

continuation = import_module("scbolt.inference._continuation")
DomainCandidateResult = continuation.DomainCandidateResult
DomainMemoryEstimator = continuation.DomainMemoryEstimator
DomainPortfolioLaunchState = continuation.DomainPortfolioLaunchState
DomainWaveLeader = continuation.DomainWaveLeader
bounded_midpoint = continuation.bounded_midpoint
build_candidate_wave = continuation.build_candidate_wave
candidate_fits_memory_budget = continuation.candidate_fits_memory_budget
continuation_base_domain = continuation.continuation_base_domain
domain_frontier_grace_seconds = continuation.domain_frontier_grace_seconds
domain_expansion_gains = continuation.domain_expansion_gains
expansion_domain_size = continuation.expansion_domain_size
initial_domain_size = continuation.initial_domain_size
minimum_domain_gain = continuation.minimum_domain_gain
outcome_counts = continuation.outcome_counts
portfolio_objective_ceiling = continuation.portfolio_objective_ceiling
reduced_domain_expansion_size = continuation.reduced_domain_expansion_size
select_best_candidate = continuation.select_best_candidate
solution_objective = continuation.solution_objective
solution_reaches_domain_ceiling = continuation.solution_reaches_domain_ceiling
solver_result_certifies_optimum = continuation.solver_result_certifies_optimum
stalled_domain_solver_settings = continuation.stalled_domain_solver_settings
terminal_refinement_solver_settings = continuation.terminal_refinement_solver_settings

complete = {f"g{i}" for i in range(20)}
current = {"g0", "g1", "g2"}

assert initial_domain_size(3, 20) == 12
assert expansion_domain_size(12, 20) == 16
assert expansion_domain_size(13, 20) == 17
assert expansion_domain_size(14, 20) == 20
assert expansion_domain_size(17, 20) == 20
assert expansion_domain_size(537, 550) == 544
assert expansion_domain_size(538, 550) == 550
assert expansion_domain_size(5177, 5198) == 5188
assert expansion_domain_size(5178, 5198) == 5198
assert reduced_domain_expansion_size(12) == 6
assert reduced_domain_expansion_size(3) == 1
assert reduced_domain_expansion_size(2) == 1
assert reduced_domain_expansion_size(1) is None
assert bounded_midpoint(3, 20) == 12
assert domain_frontier_grace_seconds(300.0) == 120.0
assert domain_frontier_grace_seconds(600.0) == 240.0
assert domain_frontier_grace_seconds(0.0) == 0.0
assert minimum_domain_gain(120, 0.10) == 12
assert minimum_domain_gain(5, 0.99) == 5
assert minimum_domain_gain(5, 0) == 0
assert minimum_domain_gain(120, 0.099) == 12
assert candidate_fits_memory_budget(45, 3, 4, cost_factor=1.10)
assert not candidate_fits_memory_budget(45, 41, 4, cost_factor=1.10)
assert candidate_fits_memory_budget(None, None, None, cost_factor=1.10)
assert candidate_fits_memory_budget(
    45,
    3,
    4,
    cost_factor=1.10,
    reserved_candidates=8,
)
assert not candidate_fits_memory_budget(
    45,
    3,
    4,
    cost_factor=1.10,
    reserved_candidates=9,
)

managed_launches = DomainPortfolioLaunchState(
    probe_required=True,
    probe_seconds=2.0,
    launch_interval_seconds=2.0,
)
assert managed_launches.ready_for_launch(0.0, has_pending=False)
managed_launches.mark_submitted(0.0)
assert not managed_launches.ready_for_launch(5.0, has_pending=True)
managed_launches.mark_probe_candidate_ready(5.0)
managed_launches.update_probe(6.9, has_pending=True)
assert not managed_launches.probe_complete
managed_launches.update_probe(7.0, has_pending=True)
assert managed_launches.probe_complete
assert managed_launches.ready_for_launch(7.0, has_pending=True)
managed_launches.mark_submitted(7.0)
assert not managed_launches.ready_for_launch(8.9, has_pending=True)
# After the initial probe, later groundings may overlap at the staggered
# interval; the coordinator reserves their projected memory separately.
assert managed_launches.ready_for_launch(9.0, has_pending=True)

failed_probe = DomainPortfolioLaunchState(
    probe_required=True,
    probe_seconds=2.0,
    launch_interval_seconds=2.0,
)
failed_probe.mark_submitted(0.0)
assert failed_probe.ready_for_launch(1.0, has_pending=False)

unmanaged_launches = DomainPortfolioLaunchState(
    probe_required=False,
    probe_seconds=2.0,
    launch_interval_seconds=0.0,
)
assert unmanaged_launches.probe_complete
assert unmanaged_launches.ready_for_launch(0.0, has_pending=True)

estimated_launches = DomainPortfolioLaunchState(
    probe_required=False,
    probe_seconds=2.0,
    launch_interval_seconds=2.0,
)
estimated_launches.mark_submitted(0.0)
assert not estimated_launches.ready_for_launch(1.9, has_pending=True)
assert estimated_launches.ready_for_launch(2.0, has_pending=True)

memory_estimator = DomainMemoryEstimator()
assert memory_estimator.estimate(domain_size=100, max_clause=1) is None
memory_estimator.observe(1000, domain_size=100, max_clause=1)
assert memory_estimator.estimate(domain_size=100, max_clause=1) == 1000
assert memory_estimator.estimate(domain_size=200, max_clause=1) == 2000
assert memory_estimator.estimate(domain_size=100, max_clause=2) == 2000
# Smaller follow-up domains retain the absolute observed floor.
assert memory_estimator.estimate(domain_size=50, max_clause=1) == 1000
memory_estimator.observe(2500, domain_size=200, max_clause=1)
assert memory_estimator.estimate(domain_size=200, max_clause=1) == 2500
assert candidate_fits_memory_budget(50, 49, 0, cost_factor=1.10)
assert domain_expansion_gains(
    ("g0", "g1"),
    ("g0", "g1", "g2"),
    {"g1", "g2"},
) == (1, 1)
assert terminal_refinement_solver_settings(
    "optN",
    "usc",
    optimum_certified=False,
) == ("opt", "bb,lin")
assert terminal_refinement_solver_settings(
    "opt",
    "bb,inc",
    optimum_certified=True,
) is None
assert terminal_refinement_solver_settings(
    "ignore",
    "bb,inc",
    optimum_certified=False,
) is None
assert terminal_refinement_solver_settings(
    "opt",
    "bb,lin",
    optimum_certified=False,
) is None
assert terminal_refinement_solver_settings(
    "optN",
    "bb,lin",
    optimum_certified=False,
) is None
assert stalled_domain_solver_settings("opt", "bb,inc") == ("opt", "bb,lin")
assert stalled_domain_solver_settings("optN", "usc") == ("opt", "bb,lin")
assert stalled_domain_solver_settings("opt", "bb,lin") is None
assert stalled_domain_solver_settings("optN", "bb,lin") is None
assert stalled_domain_solver_settings("ignore", "bb,inc") is None
assert solver_result_certifies_optimum("opt", interrupted=False)
assert solver_result_certifies_optimum("optN", interrupted=False)
assert not solver_result_certifies_optimum("opt", interrupted=True)
assert not solver_result_certifies_optimum("ignore", interrupted=False)

try:
    domain_frontier_grace_seconds(-1.0)
except ValueError:
    pass
else:
    raise AssertionError("negative domain wave patience was accepted")

assert solution_reaches_domain_ceiling(
    ("g0", "g1", "g2"),
    {"g0", "g1", "g2"},
    {"g0", "g3"},
)
assert not solution_reaches_domain_ceiling(
    ("g0", "g1"),
    {"g0", "g1", "g2"},
    {"g0", "g3"},
)
unequal_ceiling_candidates = (
    continuation.DomainCandidate(1, frozenset({"g0", "g2"})),
    continuation.DomainCandidate(2, frozenset({"g0", "g1"})),
)
assert portfolio_objective_ceiling(
    unequal_ceiling_candidates,
    {"g0", "g1"},
) == (2, 2)
assert solution_objective(
    unequal_ceiling_candidates[0].nodes,
    {"g0", "g1"},
) < portfolio_objective_ceiling(
    unequal_ceiling_candidates,
    {"g0", "g1"},
)

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
assert clause_sizes == [500, 525, 538, 550]

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
assert all(not candidate.solver_options for candidate in wave)
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
assert len(small_wave) == 8
assert len({candidate.nodes for candidate in small_wave}) == 2
assert all(candidate.solver_options for candidate in small_wave[2:])
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
assert len(full_wave) == 8
assert all(candidate.nodes == frozenset(complete) for candidate in full_wave)
assert full_wave[0].solver_options == ()
assert all(
    candidate.solver_options[1:] == ("--sign-def=rnd", "--rand-freq=0.01")
    for candidate in full_wave[1:]
)
assert len({candidate.solver_options[0] for candidate in full_wave[1:]}) == 7
assert full_wave == build_candidate_wave(
    complete,
    current,
    target_size=len(complete),
    jobs=8,
    seed=10,
    clause_bound=1,
    wave=3,
)
assert full_wave != build_candidate_wave(
    complete,
    current,
    target_size=len(complete),
    jobs=8,
    seed=11,
    clause_bound=1,
    wave=3,
)
assert full_wave != build_candidate_wave(
    complete,
    current,
    target_size=len(complete),
    jobs=8,
    seed=10,
    clause_bound=2,
    wave=3,
)
refinement_wave = build_candidate_wave(
    complete,
    complete,
    target_size=len(complete),
    jobs=8,
    seed=10,
    clause_bound=1,
    wave=4,
)
assert all(
    candidate.nodes == frozenset(complete) for candidate in refinement_wave
)
assert refinement_wave != full_wave
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

uncertified = DomainCandidateResult(
    wave[0],
    "sat",
    ("g0", "g1"),
    ("node(g0)",),
)
certified = DomainCandidateResult(
    wave[1],
    "sat",
    ("g0", "g1"),
    ("node(g0)",),
    optimum_certified=True,
)
assert select_best_candidate((uncertified, certified), {"g0"}) == certified

capacity_result = DomainCandidateResult(
    wave[2],
    "unknown",
    unknown_reason="capacity",
)
assert capacity_result.unknown_reason == "capacity"

leader = DomainWaveLeader()
assert leader.update(1, ("g0",), {"g0", "g1"}) == "improved"
assert leader.candidate_index == 1
assert leader.objective == (1, 1)
assert leader.frontier_candidates == {1}
assert leader.update(1, ("g0",), {"g0", "g1"}) == "unchanged"
assert leader.update(2, ("g0",), {"g0", "g1"}) == "joined"
assert leader.frontier_candidates == {1, 2}
assert leader.update(2, ("g0",), {"g0", "g1"}) == "unchanged"
assert leader.update(2, ("g2", "g3"), {"g0", "g1"}) == "unchanged"
assert leader.candidate_index == 1
assert leader.update(2, ("g0", "g2"), {"g0", "g1"}) == "improved"
assert leader.candidate_index == 2
assert leader.objective == (1, 2)
assert leader.frontier_candidates == {2}
assert leader.update(3, ("g0", "g3"), {"g0", "g1"}) == "joined"
assert leader.frontier_candidates == {2, 3}
assert leader.update(3, ("g0", "g1"), {"g0", "g1"}) == "improved"
assert leader.candidate_index == 3
assert leader.objective == (2, 2)
assert leader.frontier_candidates == {3}

inherited_leader = DomainWaveLeader(objective=(1, 4))
assert (
    inherited_leader.update(1, ("g0", "g2"), {"g0", "g1"})
    == "unchanged"
)
assert (
    inherited_leader.update(
        1,
        ("g0", "g2", "g3", "g4"),
        {"g0", "g1"},
    )
    == "joined"
)
assert inherited_leader.frontier_candidates == {1}
assert (
    inherited_leader.update(
        1,
        ("g0", "g2", "g3", "g4"),
        {"g0", "g1"},
    )
    == "unchanged"
)
assert (
    inherited_leader.update(
        2,
        ("g0", "g2", "g3", "g4"),
        {"g0", "g1"},
    )
    == "joined"
)
assert inherited_leader.frontier_candidates == {1, 2}

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
