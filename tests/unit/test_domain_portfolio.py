import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from scbolt.inference import _portfolio as portfolio  # noqa: E402
from scbolt.inference._continuation import (  # noqa: E402
    DomainCandidateResult,
)
from scbolt.runtime import (  # noqa: E402
    SolverDeadline,
    SolverPatience,
    format_memory_size,
    parse_memory_limit,
)

assert parse_memory_limit("") is None
assert parse_memory_limit("50") == 50_000_000_000
assert parse_memory_limit("1GiB") == 1_073_741_824
assert format_memory_size(50_000_000_000) == "50.0GB"


def run_continuation(
    complete_domain,
    *,
    initial_domain=(),
    initial_solution=(),
    initial_witness=(),
    expansion_only=False,
    strategy="bb,inc",
    max_refreshes=1,
    on_selected=lambda *_args: None,
):
    bo = SimpleNamespace(domain=SimpleNamespace(nodes=complete_domain))
    return portfolio.continue_domain_at_clause_bound(
        bo,
        max_clause=1,
        initial_domain=initial_domain,
        initial_solution=initial_solution,
        initial_witness=initial_witness,
        expansion_only=expansion_only,
        required_nodes={"g0"},
        important_nodes={"g0"},
        jobs=2,
        seed=10,
        clingo_mode="opt",
        clingo_strategy=strategy,
        clingo_configuration="auto",
        domain_patience_seconds=300.0,
        minimum_domain_yield=0.0,
        max_domain_refreshes=max_refreshes,
        clause_patience=SolverPatience(0.0),
        deadline=SolverDeadline(0.0),
        memory_limit=None,
        on_model=lambda *_args: False,
        on_selected=on_selected,
    )


def certified_domains(_bo, candidates, **_kwargs):
    return tuple(
        DomainCandidateResult(
            candidate,
            "sat",
            tuple(sorted(candidate.nodes)),
            tuple(f"node({node})" for node in sorted(candidate.nodes)),
            optimum_certified=True,
        )
        for candidate in candidates
    )


original_run_domain_wave = portfolio.run_domain_wave
try:
    portfolio.run_domain_wave = certified_domains

    selected_domains = []
    acquired = run_continuation(
        {f"g{i}" for i in range(8)},
        on_selected=lambda domain, *_args: selected_domains.append(domain),
    )
    assert acquired.complete_domain_optimal
    assert acquired.domain == frozenset({f"g{i}" for i in range(8)})
    assert acquired.solution == tuple(f"g{i}" for i in range(8))
    assert len(selected_domains) == 2

    expanded = run_continuation(
        {f"g{i}" for i in range(20)},
        initial_domain={f"g{i}" for i in range(5)},
        initial_solution={f"g{i}" for i in range(5)},
        initial_witness={f"node(g{i})" for i in range(5)},
        expansion_only=True,
    )
    assert expanded.complete_domain_optimal
    assert len(expanded.domain) == 20
    assert len(expanded.solution) == 20

    phases = []

    def unresolved_then_refreshed(_bo, candidates, *, phase, **_kwargs):
        phases.append(phase)
        if phase == "acquisition":
            return tuple(
                DomainCandidateResult(candidate, "unknown")
                for candidate in candidates
            )
        return certified_domains(_bo, candidates)

    portfolio.run_domain_wave = unresolved_then_refreshed
    refreshed = run_continuation({f"g{i}" for i in range(8)})
    assert refreshed.complete_domain_optimal
    assert phases[:2] == ["acquisition", "refresh"]

    phases.clear()

    def refine_complete_domain(_bo, candidates, *, phase, **_kwargs):
        phases.append(phase)
        if phase == "completion":
            solution = tuple(sorted(candidates[0].nodes - {"g7"}))
            return tuple(
                DomainCandidateResult(
                    candidate,
                    "sat",
                    solution,
                    tuple(f"node({node})" for node in solution),
                )
                for candidate in candidates
            )
        return certified_domains(_bo, candidates)

    portfolio.run_domain_wave = refine_complete_domain
    refined = run_continuation(
        {f"g{i}" for i in range(8)},
        initial_domain={f"g{i}" for i in range(8)},
        initial_solution={f"g{i}" for i in range(7)},
        initial_witness={f"node(g{i})" for i in range(7)},
        expansion_only=True,
    )
    assert refined.complete_domain_optimal
    assert refined.terminal_refinement_used
    assert phases == ["completion", "refinement"]
finally:
    portfolio.run_domain_wave = original_run_domain_wave

print("domain portfolio tests passed")
