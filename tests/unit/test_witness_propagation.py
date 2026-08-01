import json
import subprocess
import sys
import tempfile
from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

should_forward = import_module(
    "scbolt.inference"
).should_forward_previous_solution

# RELAXED or SEED forwards only when it adds no constraints and has no valid
# warm start. LOCK always solves when an upstream witness is available.
assert should_forward(False, ())
assert not should_forward(True, ())
assert not should_forward(False, ("node(a)",))
assert not should_forward(True, ("node(a)",))

makefile = (REPO_ROOT / "Makefile").read_text()
lock_recipe = makefile.split(
    "$(max_nodes_lock) $(max_nodes_lock_witness) &:", 1
)[1].split("$(bn_min):", 1)[0]
assert "metadata_solution_field,$(word 7,$^),forwarded-from" in lock_recipe
assert "--filter-grn $(word 6,$^)" in lock_recipe
assert "$(max_consts_soft)" not in lock_recipe

with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    source = directory / "relaxed.txt"
    target = directory / "seed.txt"
    params = directory / "params.mk"
    source.touch()
    target.touch()
    params.touch()

    metadata = REPO_ROOT / "scripts" / "utils" / "scbolt_metadata.py"
    subprocess.run(
        [
            sys.executable,
            str(metadata),
            "write",
            "--module",
            "max-nodes-seed",
            "--target",
            str(target),
            "--params-file",
            str(params),
            "--git-hash",
            "test",
            "--solution-status",
            "partial",
            "--solution-kept",
            "8",
            "--solution-total",
            "10",
            "--solution-forwarded-from",
            str(source),
        ],
        check=True,
    )
    payload = json.loads(target.with_suffix(".scbolt.json").read_text())
    assert payload["solution"] == {
        "coverage": "8/10",
        "forwarded_from": str(source),
        "kept": 8,
        "status": "partial",
        "total": 10,
    }
