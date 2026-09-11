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
assert "metadata_solution_field,$(max_nodes_seed_solution),forwarded-from" in lock_recipe
assert "--filter-grn $(full_input)" in lock_recipe
assert "--initial-witness $(max_nodes_seed_witness)" in lock_recipe

consts_recipe = makefile.split(
    "$(max_consts) $(max_consts_witness) &:", 1
)[1].split("$(max_nodes_relaxed)", 1)[0]
assert "--filter-grn $(consts_input)" in consts_recipe
assert "--initial-witness $(consts_input_witness)" in consts_recipe
assert "--witness $(max_consts_witness)" in consts_recipe
assert "--bonesis-mode $(consts_mode)" in consts_recipe

relaxed_recipe = makefile.split(
    "$(max_nodes_relaxed) $(max_nodes_relaxed_witness) &:", 1
)[1].split("$(max_nodes_seed)&:", 1)[0]
assert "--filter-grn $(relaxed_input)" in relaxed_recipe
assert "--forward-witness $(relaxed_input_witness)" in relaxed_recipe

seed_recipe = makefile.split("$(max_nodes_seed)&:", 1)[1].split(
    "$(max_nodes_lock)", 1
)[0]
assert "--filter-grn $(full_input)" in seed_recipe
assert "--forward-witness $(full_input_witness)" in seed_recipe

submin_recipe = makefile.split("$(bn_submin)&:", 1)[1].split(
    "$(bn_diverse)&:", 1
)[0]
assert "--filter-grn $(final_selection)" in submin_recipe
assert "--initial-witness $(final_selection_witness)" in submin_recipe

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
