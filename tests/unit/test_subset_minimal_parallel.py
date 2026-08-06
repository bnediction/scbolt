import sys
import tempfile
from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

get_subset_minimal_clingo_settings = import_module(
    "scbolt.runtime"
).get_subset_minimal_clingo_settings
enumeration = import_module("scbolt.inference._enumeration")
BooleanNetworkEnumerationCheckpoint = (
    enumeration.BooleanNetworkEnumerationCheckpoint
)
build_subset_minimal_blockers = enumeration.build_subset_minimal_blockers
enumeration_fingerprint = enumeration.enumeration_fingerprint

assert get_subset_minimal_clingo_settings("1") == {}
assert get_subset_minimal_clingo_settings("2") == {"parallel": 2}
assert get_subset_minimal_clingo_settings("16") == {"parallel": 14}
assert get_subset_minimal_clingo_settings("64") == {"parallel": 14}
assert get_subset_minimal_clingo_settings("4,split") == {
    "parallel": None,
    "clingo_options": ["--parallel-mode=4,split"],
}

blockers = build_subset_minimal_blockers(
    [
        {("A", "B", 1), ("B", "C", -1)},
        {("A", "B", 1), ("B", "C", -1)},
        {("quoted\"node", "C", 1)},
    ]
)
assert sum(
    line.startswith("scbolt_checkpoint_solution(")
    for line in blockers.splitlines()
) == 2
assert "scbolt_checkpoint_present(L,N,S) :- clause(N,C,L,S)" in blockers
assert "not scbolt_checkpoint_missing(I)" in blockers
assert 'scbolt_checkpoint_edge(2,"quoted\\\"node","C",1)' in blockers

try:
    build_subset_minimal_blockers([{("A", "B", 0)}])
except ValueError as error:
    assert "unsupported influence edge sign" in str(error)
else:
    raise AssertionError("unsigned checkpoint influence edge was accepted")


def write_complete_solution(checkpoint, index):
    with checkpoint.atomic_solution_directory(index) as directory:
        for filename in checkpoint.required_output_names():
            (directory / filename).touch()


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    input_file = root / "model.bo"
    input_file.write_text("model-v1\n", encoding="utf-8")
    fingerprint = enumeration_fingerprint(
        [input_file],
        {"max_clauses": 4},
    )
    checkpoint = BooleanNetworkEnumerationCheckpoint(
        root / "solutions",
        config_formats=("csv",),
        graph_formats=("dot",),
        fingerprint=fingerprint,
    )
    recovery = checkpoint.prepare()
    assert recovery.solution_directories == ()
    assert recovery.reset_reason is None

    write_complete_solution(checkpoint, 1)
    checkpoint.write_state(solution_count=1, elapsed_seconds=42.5)
    incomplete = checkpoint.outdir / "2"
    incomplete.mkdir()
    (incomplete / "model.bnet").touch()

    recovered = checkpoint.prepare()
    assert tuple(path.name for path in recovered.solution_directories) == ("1",)
    assert tuple(path.name for path in recovered.discarded_directories) == ("2",)
    assert recovered.elapsed_seconds == 42.5
    assert not incomplete.exists()

    try:
        with checkpoint.atomic_solution_directory(2) as directory:
            (directory / "model.bnet").touch()
            raise RuntimeError("interrupted write")
    except RuntimeError:
        pass
    else:
        raise AssertionError("interrupted atomic output write was suppressed")
    assert not (checkpoint.outdir / "2").exists()
    assert not (checkpoint.outdir / ".solution-2.tmp").exists()

    changed = BooleanNetworkEnumerationCheckpoint(
        checkpoint.outdir,
        config_formats=("csv",),
        graph_formats=("dot",),
        fingerprint=enumeration_fingerprint(
            [input_file],
            {"max_clauses": 5},
        ),
    ).prepare()
    assert changed.reset_reason == "enumeration inputs changed"
    assert changed.solution_directories == ()
    assert not (checkpoint.outdir / "1").exists()

print("subset-minimal enumeration tests passed")
