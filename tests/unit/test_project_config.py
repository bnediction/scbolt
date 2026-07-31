#!/usr/bin/env python3
"""Unit tests for the public scbolt.yml loader."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "scripts" / "utils" / "project_config.py"


def run_helper(command: str, content: str, *args: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "scbolt.yml"
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
        return subprocess.run(
            ["python3", str(HELPER), command, str(path), *args],
            check=False,
            capture_output=True,
            text=True,
        )


def exported(content: str) -> dict[str, str]:
    result = run_helper("export", content)
    if result.returncode:
        raise AssertionError(result.stderr)
    return dict(line.split("\t", 1) for line in result.stdout.splitlines())


class ProjectConfigurationTests(unittest.TestCase):
    def test_compact_and_vertical_lists_are_equivalent(self) -> None:
        compact = exported("labels: [Prom1, Prom2, Rep]\n")
        vertical = exported(
            """
            labels:
              - Prom1
              - Prom2
              - Rep
            """
        )
        self.assertEqual(compact["LABEL"], "Prom1 Prom2 Rep")
        self.assertEqual(compact, vertical)

    def test_condition_mapping_and_flat_keys_are_equivalent(self) -> None:
        mapped = exported(
            """
            conditions: [ctrl, treated]
            gsm:
              ctrl: GSM1
              treated: GSM2
            knnsc-centrality:
              ctrl: [Prom1, Prom2]
              treated: [Prom1]
            """
        )
        flattened = exported(
            """
            conditions: [ctrl, treated]
            gsm-ctrl: GSM1
            gsm-treated: GSM2
            knnsc-centrality-ctrl: [Prom1, Prom2]
            knnsc-centrality-treated: [Prom1]
            """
        )
        internal = {
            key: value
            for key, value in mapped.items()
            if not key.startswith("SCBOLT_PUBLIC_PARAMETER_")
        }
        other = {
            key: value
            for key, value in flattened.items()
            if not key.startswith("SCBOLT_PUBLIC_PARAMETER_")
        }
        self.assertEqual(internal, other)
        self.assertEqual(internal["GSM_CTRL"], "GSM1")
        self.assertEqual(internal["KNNSC_CENTRALITY_CTRL"], "Prom1 Prom2")
        self.assertEqual(
            mapped["SCBOLT_PUBLIC_PARAMETER_KNNSC_CENTRALITY_CTRL"],
            "knnsc-centrality-ctrl",
        )

    def test_condition_file_mapping_and_flat_keys_are_equivalent(self) -> None:
        mapped = exported(
            """
            conditions: [ctrl, treated]
            count-file:
              ctrl: ctrl.h5ad
              treated: treated.h5ad
            macrostate-file:
              ctrl: ctrl_mstates.h5ad
              treated: treated_mstates.h5ad
            """
        )
        flattened = exported(
            """
            conditions: [ctrl, treated]
            count-file-ctrl: ctrl.h5ad
            count-file-treated: treated.h5ad
            macrostate-file-ctrl: ctrl_mstates.h5ad
            macrostate-file-treated: treated_mstates.h5ad
            """
        )
        internal = {
            key: value
            for key, value in mapped.items()
            if not key.startswith("SCBOLT_PUBLIC_PARAMETER_")
        }
        other = {
            key: value
            for key, value in flattened.items()
            if not key.startswith("SCBOLT_PUBLIC_PARAMETER_")
        }
        self.assertEqual(internal, other)
        self.assertEqual(internal["COUNT_FILE_CTRL"], "ctrl.h5ad")
        self.assertEqual(
            internal["MACROSTATE_FILE_TREATED"],
            "treated_mstates.h5ad",
        )
        self.assertEqual(
            mapped["SCBOLT_PUBLIC_PARAMETER_COUNT_FILES"],
            "count-file",
        )
        self.assertEqual(
            mapped["SCBOLT_PUBLIC_PARAMETER_MACROSTATE_FILES"],
            "macrostate-file",
        )

    def test_shared_macrostate_file_is_allowed_with_named_conditions(self) -> None:
        settings = exported(
            """
            conditions: [ctrl, treated]
            macrostate-file: all_mstates.h5ad
            """
        )
        self.assertEqual(settings["MACROSTATE_FILE"], "all_mstates.h5ad")

    def test_shared_and_conditional_macrostate_files_are_rejected(self) -> None:
        result = run_helper(
            "export",
            """
            conditions: [ctrl, treated]
            macrostate-file: all_mstates.h5ad
            macrostate-file-ctrl: ctrl_mstates.h5ad
            """,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "configuration key 'macrostate-file' cannot combine a shared file "
            "with condition-specific files",
            result.stderr,
        )

    def test_plural_input_file_keys_are_rejected(self) -> None:
        for key in (
            "count-files",
            "macrostate-files",
            "count_files",
            "macrostate_files",
        ):
            with self.subTest(key=key):
                result = run_helper("export", f"{key}: []\n")
                self.assertEqual(result.returncode, 1)
                self.assertIn(
                    f"unknown configuration key '{key}'",
                    result.stderr,
                )

    def test_conditions_are_inferred_in_first_appearance_order(self) -> None:
        settings = exported(
            """
            gsm-treated: GSM2
            gsm-ctrl: GSM1
            """
        )
        self.assertEqual(settings["CONDITIONS"], "treated ctrl")

    def test_omics_and_bin_hvg_values_are_independent(self) -> None:
        settings = exported(
            """
            omics-hvg-method: loess
            omics-hvg-top: null
            bin-hvg-method: binning
            bin-hvg-top: 500
            """
        )
        self.assertEqual(settings["OMICS_HVG_METHOD"], "loess")
        self.assertEqual(settings["BIN_HVG_METHOD"], "binning")
        self.assertEqual(settings["OMICS_HVG_TOP"], "")
        self.assertEqual(settings["BIN_HVG_TOP"], "500")

    def test_bin_include_nodes_uses_short_public_name(self) -> None:
        settings = exported(
            "bin-include-nodes: [Rara, Cebpa, Spi1]\n",
        )
        self.assertEqual(settings["BIN_INCLUDE_NODES"], "Rara Cebpa Spi1")

        result = run_helper(
            "export",
            "binarization-include-nodes: [Rara, Cebpa, Spi1]\n",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "unknown configuration key 'binarization-include-nodes'",
            result.stderr,
        )

    def test_shared_and_deprecated_hvg_keys_are_rejected(self) -> None:
        for key in (
            "hvg-method",
            "analysis-hvg-method",
            "binarization-hvg-method",
        ):
            with self.subTest(key=key):
                result = run_helper("export", f"{key}: loess\n")
                self.assertEqual(result.returncode, 1)
                self.assertIn(
                    f"unknown configuration key '{key}'",
                    result.stderr,
                )

    def test_public_keys_use_kebab_case(self) -> None:
        settings = exported("alignment-tool: cellranger\n")
        self.assertEqual(settings["ALIGNMENT_TOOL"], "cellranger")

        result = run_helper("export", "alignment_tool: cellranger\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "unknown configuration key 'alignment_tool'",
            result.stderr,
        )

    def test_hyphenated_condition_uses_a_valid_internal_suffix(self) -> None:
        settings = exported(
            """
            conditions: [control, treatment-a]
            gsm-treatment-a: GSM2
            """
        )
        self.assertEqual(settings["GSM_TREATMENT_A"], "GSM2")

    def test_native_yaml_types_are_preserved(self) -> None:
        settings = exported(
            """
            zeroes-are-zeroes: false
            neighbors: 14
            resolution: 0.4
            omics-hvg-top: null
            """
        )
        self.assertEqual(settings["ZEROES_ARE_ZEROES"], "false")
        self.assertEqual(settings["NEIGHBORS"], "14")
        self.assertEqual(settings["RESOLUTION"], "0.4")
        self.assertEqual(settings["OMICS_HVG_TOP"], "")

    def test_unknown_key_reports_its_location(self) -> None:
        result = run_helper("export", "neigbors: 14\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn(":1:1: unknown configuration key 'neigbors'", result.stderr)

    def test_duplicate_key_reports_both_definitions(self) -> None:
        result = run_helper(
            "export",
            "neighbors: 14\nneighbors: 15\n",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            ":2:1: duplicate configuration key 'neighbors' "
            "(first defined at line 1)",
            result.stderr,
        )

    def test_quoted_boolean_is_rejected(self) -> None:
        result = run_helper("export", "zeroes-are-zeroes: 'false'\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("must be a boolean", result.stderr)

    def test_version_key_is_rejected(self) -> None:
        result = run_helper("export", "version: 1\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown configuration key 'version'", result.stderr)

    def test_condition_not_declared_is_rejected(self) -> None:
        result = run_helper(
            "export",
            """
            conditions: [ctrl]
            gsm:
              treated: GSM2
            """,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("condition 'treated' in gsm is not listed in conditions", result.stderr)

    def test_conflicting_conditional_forms_are_rejected(self) -> None:
        result = run_helper(
            "export",
            """
            gsm:
              ctrl: GSM1
            gsm-ctrl: GSM2
            """,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("conflicting values for condition 'ctrl' in gsm", result.stderr)


if __name__ == "__main__":
    unittest.main()
