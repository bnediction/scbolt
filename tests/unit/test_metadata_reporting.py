import importlib.util
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_SCRIPT = REPO_ROOT / "scripts" / "utils" / "scbolt_metadata.py"

spec = importlib.util.spec_from_file_location("scbolt_metadata", METADATA_SCRIPT)
assert spec is not None and spec.loader is not None
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)

assert metadata.format_node_list_change("", "A B C") == "3 nodes missing"
assert metadata.format_node_list_change("A B C", "B C D E") == (
    "2 nodes missing, 1 extra node"
)
assert metadata.format_node_list_change("A B", "B A") == "nodes reordered"
assert metadata.format_parameter_change("SEED", "1", "2") == "1 -> 2"
assert metadata.public_parameter_name("BIN_INCLUDE_NODES") == "bin-include-nodes"

reports = [
    (
        "load-matrix",
        {
            "status": "stale",
            "message": "load-matrix (runtime drift: scbolt-core)",
        },
    ),
    (
        "filtering",
        {
            "status": "stale",
            "message": "filtering (runtime drift: scbolt-core)",
        },
    ),
    (
        "normalization",
        {
            "status": "stale",
            "message": "normalization (SEED: 1 -> 2)",
        },
    ),
]

metadata.add_stale_report_groups(reports)

for _module, fields in reports[:2]:
    assert fields["stale-group-id"] == "1"
    assert fields["stale-group-modules"] == "load-matrix filtering"

assert "stale-group-id" not in reports[2][1]

with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    fake_make = directory / "fake-make"
    fake_python = directory / "fake-python"
    makefile = directory / "Makefile"

    fake_make.write_text("#!/bin/sh\nprintf 'manifest\\n'\n")
    fake_make.chmod(0o755)
    fake_python.write_text(
        """#!/bin/sh
printf '%b\n' \\
  'load-matrix\tstatus\tstale' \\
  'load-matrix\tmessage\tload-matrix (runtime drift: scbolt-core)' \\
  'load-matrix\tdeps\t' \\
  'load-matrix\tstale-group-id\t1' \\
  'load-matrix\tstale-group-modules\tload-matrix filtering normalization' \\
  'filtering\tstatus\tstale' \\
  'filtering\tmessage\tfiltering (runtime drift: scbolt-core)' \\
  'filtering\tdeps\tload-matrix' \\
  'filtering\tstale-group-id\t1' \\
  'filtering\tstale-group-modules\tload-matrix filtering normalization' \\
  'normalization\tstatus\tstale' \\
  'normalization\tmessage\tnormalization (runtime drift: scbolt-core)' \\
  'normalization\tdeps\tfiltering' \\
  'normalization\tstale-group-id\t1' \\
  'normalization\tstale-group-modules\tload-matrix filtering normalization' \\
  'bin-cells\tstatus\tstale' \\
  'bin-cells\tmessage\tbin-cells (bin-include-nodes: 37 nodes missing)' \\
  'bin-cells\tdeps\t' \\
  'bin-cells\tstale-group-id\t2' \\
  'bin-cells\tstale-group-modules\tbin-cells bin-dea bin-consensus' \\
  'bin-dea\tstatus\tstale' \\
  'bin-dea\tmessage\tbin-dea (bin-include-nodes: 37 nodes missing)' \\
  'bin-dea\tdeps\t' \\
  'bin-dea\tstale-group-id\t2' \\
  'bin-dea\tstale-group-modules\tbin-cells bin-dea bin-consensus' \\
  'bin-consensus\tstatus\tstale' \\
  'bin-consensus\tmessage\tbin-consensus (bin-include-nodes: 37 nodes missing)' \\
  'bin-consensus\tdeps\tbin-cells bin-dea' \\
  'bin-consensus\tstale-group-id\t2' \\
  'bin-consensus\tstale-group-modules\tbin-cells bin-dea bin-consensus'
"""
    )
    fake_python.chmod(0o755)
    makefile.write_text(
        f"""SHELL := /bin/bash
scbolt_root := {REPO_ROOT}
PARAMS := {REPO_ROOT / 'tests' / 'fixtures' / 'params.mk'}

include $(scbolt_root)/make/config.mk
include $(scbolt_root)/make/modules.mk

override reset_stages := load-matrix filtering normalization bin-cells bin-dea bin-consensus
override target_dry_run_modules = $(reset_stages)
override target_run_modules =
override reset_modules :=
override nested_make := {fake_make}
override python := {fake_python}
print_warning = printf '%s\\n' "WARNING - $(1)"

.PHONY: inspect
inspect:
\t@$(call warn_stale_outputs,spec)
"""
    )

    result = subprocess.run(
        ["make", "-s", "-f", str(makefile), "inspect"],
        check=True,
        capture_output=True,
        text=True,
    )
    expected_output = [
        "WARNING - stale module outputs: load-matrix, filtering, normalization",
        "    - runtime drift: scbolt-core",
        "WARNING - stale module outputs: bin-cells, bin-dea, bin-consensus",
        "    - bin-include-nodes: 37 nodes missing",
    ]
    assert result.stdout.splitlines() == expected_output, (
        result.stdout,
        result.stderr,
    )

    many_modules = [f"module-{index}" for index in range(96)]
    fake_python.write_text(
        "#!/bin/sh\n"
        + "".join(
            f"printf '%b\\n' '{module}\\tstatus\\tdone' "
            f"'{module}\\tmessage\\t{module}' "
            f"'{module}\\tdeps\\t'\n"
            for module in many_modules
        )
    )
    makefile.write_text(
        f"""SHELL := /bin/bash
scbolt_root := {REPO_ROOT}
PARAMS := {REPO_ROOT / 'tests' / 'fixtures' / 'params.mk'}

include $(scbolt_root)/make/config.mk
include $(scbolt_root)/make/modules.mk

override reset_stages := {' '.join(many_modules)}
override target_dry_run_modules = $(reset_stages)
override target_run_modules =
override reset_modules :=
override nested_make := {fake_make}
override python := {fake_python}
print_warning = printf '%s\\n' "WARNING - $(1)"

.PHONY: inspect
inspect:
\t@$(call warn_stale_outputs,spec)
"""
    )

    result = subprocess.run(
        ["make", "-s", "-f", str(makefile), "inspect"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
