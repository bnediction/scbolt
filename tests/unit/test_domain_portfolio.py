import io
import sys
from pathlib import Path
from types import SimpleNamespace

from tqdm.utils import disp_len

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
assert portfolio._domain_progress_layout(16, 18) == (17, None)
assert portfolio._domain_progress_layout(16, 17) == (16, 16)

progress_output = io.StringIO()
progress = portfolio.ptqdm(
    total=float("inf"),
    desc="Domain acquisition [candidate=16/16]",
    file=progress_output,
    bar_format="{desc}: {n_fmt:>4}it ({elapsed}{postfix})",
    dynamic_ncols=False,
    ncols=96,
)
progress.set_postfix(
    {
        "important": "0/5",
        "total": "   0/4588",
        "state": "interrupted",
    },
    refresh=False,
)
rendered_progress = str(progress)
progress.close()
assert disp_len(rendered_progress) <= 96
assert "important=0/5, total=   0/4588, state=" in rendered_progress

original_internal_wave = portfolio._run_domain_wave
original_current_rss = portfolio.current_rss_bytes
original_release_memory = portfolio.release_unused_memory
original_print_debug = portfolio.console.print_debug
memory_release_events = []
debug_messages = []


def interrupted_domain_wave(*_args, **_kwargs):
    raise KeyboardInterrupt


try:
    portfolio._run_domain_wave = interrupted_domain_wave
    portfolio.current_rss_bytes = lambda: 1_000_000_000
    portfolio.release_unused_memory = lambda: memory_release_events.append("released")
    portfolio.console.print_debug = lambda message, **_kwargs: debug_messages.append(
        message
    )
    try:
        portfolio.run_domain_wave(
            SimpleNamespace(),
            (),
            phase="acquisition",
            wave=1,
            max_clause=1,
            witness=(),
            incumbent_solution=(),
            clingo_mode="opt",
            clingo_strategy="bb,inc",
            clingo_configuration="auto",
            patience_seconds=300.0,
            clause_patience=SolverPatience(0.0),
            deadline=SolverDeadline(0.0),
            important_nodes=set(),
            memory_limit=50_000_000_000,
            on_model=lambda *_args: False,
        )
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("domain-wave interruption was suppressed")
finally:
    portfolio._run_domain_wave = original_internal_wave
    portfolio.current_rss_bytes = original_current_rss
    portfolio.release_unused_memory = original_release_memory
    portfolio.console.print_debug = original_print_debug

assert memory_release_events == ["released"]
assert debug_messages == []


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

    phases.clear()

    def unresolved_complete_domain(_bo, candidates, *, phase, **_kwargs):
        phases.append(phase)
        return tuple(
            DomainCandidateResult(candidate, "unknown") for candidate in candidates
        )

    portfolio.run_domain_wave = unresolved_complete_domain
    retained_solution = tuple(f"g{i}" for i in range(7))
    retained_witness = tuple(f"node(g{i})" for i in range(7))
    unresolved = run_continuation(
        {f"g{i}" for i in range(8)},
        initial_domain={f"g{i}" for i in range(8)},
        initial_solution=retained_solution,
        initial_witness=retained_witness,
        expansion_only=True,
        strategy="bb,lin",
    )
    assert unresolved.continuation_exhausted
    assert not unresolved.complete_domain_unsat
    assert not unresolved.complete_domain_optimal
    assert unresolved.solution == retained_solution
    assert unresolved.witness == retained_witness
    assert phases == ["completion"]

    phases.clear()

    def unresolved_refinement(_bo, candidates, *, phase, **_kwargs):
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
        return tuple(
            DomainCandidateResult(candidate, "unknown") for candidate in candidates
        )

    portfolio.run_domain_wave = unresolved_refinement
    unresolved = run_continuation(
        {f"g{i}" for i in range(8)},
        initial_domain={f"g{i}" for i in range(8)},
        initial_solution=retained_solution,
        initial_witness=retained_witness,
        expansion_only=True,
    )
    assert unresolved.continuation_exhausted
    assert unresolved.terminal_refinement_used
    assert unresolved.solution == retained_solution
    assert unresolved.witness == retained_witness
    assert phases == ["completion", "refinement"]

    def capacity_limited_complete_domain(_bo, candidates, **_kwargs):
        return tuple(
            DomainCandidateResult(
                candidate,
                "unknown",
                unknown_reason="capacity",
            )
            for candidate in candidates
        )

    portfolio.run_domain_wave = capacity_limited_complete_domain
    try:
        run_continuation(
            {f"g{i}" for i in range(8)},
            initial_domain={f"g{i}" for i in range(8)},
            initial_solution=retained_solution,
            initial_witness=retained_witness,
            expansion_only=True,
            strategy="bb,lin",
        )
    except portfolio.SolverCapacityError:
        pass
    else:
        raise AssertionError("complete-domain capacity failure was suppressed")
finally:
    portfolio.run_domain_wave = original_run_domain_wave

print("domain portfolio tests passed")
