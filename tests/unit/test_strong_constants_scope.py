"""Routing tests for the configurable strong-constant selection stage."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
PARAMS = REPO_ROOT / "tests" / "fixtures" / "params.mk"
METADATA = REPO_ROOT / "scripts" / "utils" / "scbolt_metadata.py"

ROUTE_QUERY = """\
.PHONY: __strong-constants-route
__strong-constants-route:
\t@printf '%s\\t%s\\n' \\
\t\t'scope' '$(STRONG_CONSTANTS_SCOPE)' \\
\t\t'enabled' '$(strong_constants_enabled)' \\
\t\t'consts-input' '$(consts_input)' \\
\t\t'consts-witness' '$(consts_input_witness)' \\
\t\t'consts-mode' '$(consts_mode)' \\
\t\t'relaxed-input' '$(relaxed_input)' \\
\t\t'relaxed-witness' '$(relaxed_input_witness)' \\
\t\t'full-input' '$(full_input)' \\
\t\t'full-witness' '$(full_input_witness)' \\
\t\t'final-selection' '$(final_selection)' \\
\t\t'final-witness' '$(final_selection_witness)' \\
\t\t'stages' '$(strip $(gene_selection_stages))' \\
\t\t'sensitive-consts' '$(sensitive_params_max-consts)' \\
\t\t'sensitive-relaxed' '$(sensitive_params_max-nodes-relaxed)' \\
\t\t'sensitive-seed' '$(sensitive_params_max-nodes-seed)' \\
\t\t'sensitive-lock' '$(sensitive_params_max-nodes-lock)' \\
\t\t'sensitive-bn' '$(sensitive_params_bn-submin)'
"""


def make_route(scope: str) -> dict[str, str]:
    result = subprocess.run(
        [
            "make",
            "-s",
            "-f",
            str(MAKEFILE),
            f"PARAMS={PARAMS}",
            f"STRONG_CONSTANTS_SCOPE={scope}",
            f"--eval={ROUTE_QUERY}",
            "__strong-constants-route",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("\t", 1) for line in result.stdout.splitlines())


def dry_run(scope: str) -> str:
    result = subprocess.run(
        [
            "make",
            "-s",
            "--always-make",
            "--dry-run",
            "-f",
            str(MAKEFILE),
            f"PARAMS={PARAMS}",
            "LOGGING=false",
            "__check_mode=true",
            f"STRONG_CONSTANTS_SCOPE={scope}",
            "__bn-submin",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def assert_endswith(value: str, suffix: str) -> None:
    assert value.endswith(suffix), f"{value!r} does not end with {suffix!r}"


expected_routes = {
    "soft": {
        "consts-input": "soft/comps.txt",
        "consts-witness": "soft/witness.lp",
        "consts-mode": "soft",
        "relaxed-input": "consts/comps.txt",
        "relaxed-witness": "consts/witness.lp",
        "full-input": "relaxed/comps.txt",
        "full-witness": "relaxed/witness.lp",
        "final-selection": "lock/comps.txt",
        "final-witness": "lock/witness.lp",
        "stages": "max-nodes-soft max-consts max-nodes-relaxed "
        "max-nodes-seed max-nodes-lock",
    },
    "relaxed": {
        "consts-input": "relaxed/comps.txt",
        "consts-witness": "relaxed/witness.lp",
        "consts-mode": "relaxed",
        "relaxed-input": "soft/comps.txt",
        "relaxed-witness": "soft/witness.lp",
        "full-input": "consts/comps.txt",
        "full-witness": "consts/witness.lp",
        "final-selection": "lock/comps.txt",
        "final-witness": "lock/witness.lp",
        "stages": "max-nodes-soft max-nodes-relaxed max-consts "
        "max-nodes-seed max-nodes-lock",
    },
    "full": {
        "consts-input": "lock/comps.txt",
        "consts-witness": "lock/witness.lp",
        "consts-mode": "hard",
        "relaxed-input": "soft/comps.txt",
        "relaxed-witness": "soft/witness.lp",
        "full-input": "relaxed/comps.txt",
        "full-witness": "relaxed/witness.lp",
        "final-selection": "consts/comps.txt",
        "final-witness": "consts/witness.lp",
        "stages": "max-nodes-soft max-nodes-relaxed max-nodes-seed "
        "max-nodes-lock max-consts",
    },
    "none": {
        "consts-input": "",
        "consts-witness": "",
        "consts-mode": "",
        "relaxed-input": "soft/comps.txt",
        "relaxed-witness": "soft/witness.lp",
        "full-input": "relaxed/comps.txt",
        "full-witness": "relaxed/witness.lp",
        "final-selection": "lock/comps.txt",
        "final-witness": "lock/witness.lp",
        "stages": "max-nodes-soft max-nodes-relaxed max-nodes-seed "
        "max-nodes-lock",
    },
}

for scope, expected in expected_routes.items():
    route = make_route(scope)
    assert route["scope"] == scope
    assert route["enabled"] == (scope if scope != "none" else "")
    for name, value in expected.items():
        if name in {"consts-mode", "stages"} or not value:
            assert route[name] == value
        else:
            assert_endswith(route[name], f"/infer/genes/{value}")

    for name in (
        "sensitive-consts",
        "sensitive-relaxed",
        "sensitive-seed",
        "sensitive-lock",
        "sensitive-bn",
    ):
        assert "STRONG_CONSTANTS_SCOPE" in route[name].split()

    output = dry_run(scope)
    expected_stages = expected["stages"].split()
    stage_positions = [
        output.index(f'"RULE" "{stage}"') for stage in expected_stages
    ]
    assert stage_positions == sorted(stage_positions)

    expected_const_runs = 0 if scope == "none" else 1
    assert output.count("selection.py filter-consts") == expected_const_runs
    if scope != "none":
        const_start = output.index("selection.py filter-consts")
        const_end = output.find('"RULE"', const_start)
        const_command = output[const_start:const_end]
        assert f"--filter-grn {route['consts-input']}" in const_command
        assert f"--initial-witness {route['consts-witness']}" in const_command
        assert f"--bonesis-mode {route['consts-mode']}" in const_command

    inference_start = output.index("infer.py submin")
    inference_command = output[inference_start:]
    assert f"--filter-grn {route['final-selection']}" in inference_command
    assert f"--initial-witness {route['final-witness']}" in inference_command

invalid = subprocess.run(
    [
        "make",
        "-s",
        "-f",
        str(MAKEFILE),
        f"PARAMS={PARAMS}",
        "STRONG_CONSTANTS_SCOPE=early",
        "bn-submin",
    ],
    cwd=REPO_ROOT,
    check=False,
    capture_output=True,
    text=True,
)
assert invalid.returncode != 0
assert "supported values: soft, relaxed, full, none" in invalid.stderr

invalid_check = subprocess.run(
    [
        "make",
        "-s",
        "-f",
        str(MAKEFILE),
        f"PARAMS={PARAMS}",
        "PROJECT_DIR=/tmp/scbolt-invalid-strong-constants-scope",
        "TARGET=max-consts",
        "STRONG_CONSTANTS_SCOPE=early",
        "__check_externals__=false",
        "check",
    ],
    cwd=REPO_ROOT,
    check=False,
    capture_output=True,
    text=True,
)
assert invalid_check.returncode != 0
assert (
    "unsupported value for method parameter STRONG_CONSTANTS_SCOPE"
    in invalid_check.stdout
)
assert "supported values: soft, relaxed, full, none" in invalid_check.stdout

disabled = subprocess.run(
    [
        "make",
        "-s",
        "-f",
        str(MAKEFILE),
        f"PARAMS={PARAMS}",
        "STRONG_CONSTANTS_SCOPE=none",
        "__max-consts",
    ],
    cwd=REPO_ROOT,
    check=True,
    capture_output=True,
    text=True,
)
assert "strong-constants-scope: none" in disabled.stdout

with tempfile.TemporaryDirectory() as directory:
    directory_path = Path(directory)
    target = directory_path / "comps.txt"
    params = directory_path / "params.yml"
    target.write_text("A\nB\n", encoding="utf-8")
    params.write_text("strong-constants-scope: full\n", encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(METADATA),
            "write",
            "--module",
            "max-consts",
            "--target",
            str(target),
            "--params-file",
            str(params),
            "--git-hash",
            "test",
            "--param",
            "STRONG_CONSTANTS_SCOPE=full",
            "--solution-status",
            "partial",
            "--solution-kept",
            "2",
            "--solution-total",
            "3",
            "--strong-constants-requested-scope",
            "full",
            "--strong-constants-executed-scope",
            "full",
            "--strong-constants-bonesis-mode",
            "hard",
        ],
        check=True,
    )
    payload = json.loads(target.with_suffix(".scbolt.json").read_text())
    assert payload["strong_constants"] == {
        "bonesis_mode": "hard",
        "executed_scope": "full",
        "input_components": 3,
        "requested_scope": "full",
        "retained_components": 2,
        "status": "partial",
    }

    stale = subprocess.run(
        [
            sys.executable,
            str(METADATA),
            "state",
            "--module",
            "max-consts",
            "--target",
            str(target),
            "--param",
            "STRONG_CONSTANTS_SCOPE=relaxed",
            "--field",
            "status",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert stale.stdout.strip() == "stale"
