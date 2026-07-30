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
            knnsc_centrality:
              ctrl: [Prom1, Prom2]
              treated: [Prom1]
            """
        )
        flattened = exported(
            """
            conditions: [ctrl, treated]
            gsm_ctrl: GSM1
            gsm_treated: GSM2
            knnsc_centrality_ctrl: [Prom1, Prom2]
            knnsc_centrality_treated: [Prom1]
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

    def test_conditions_are_inferred_in_first_appearance_order(self) -> None:
        settings = exported(
            """
            gsm_treated: GSM2
            gsm_ctrl: GSM1
            """
        )
        self.assertEqual(settings["CONDITIONS"], "treated ctrl")

    def test_shared_hvg_values_fan_out_and_specific_value_wins(self) -> None:
        settings = exported(
            """
            hvg_method: binning
            analysis_hvg_method: loess
            hvg_top: null
            """
        )
        self.assertEqual(settings["ANALYSIS_HVG_METHOD"], "loess")
        self.assertEqual(settings["BIN_HVG_METHOD"], "binning")
        self.assertEqual(settings["ANALYSIS_HVG_TOP"], "")
        self.assertEqual(settings["BIN_HVG_TOP"], "")

    def test_native_yaml_types_are_preserved(self) -> None:
        settings = exported(
            """
            zeroes_are_zeroes: false
            neighbors: 14
            resolution: 0.4
            analysis_hvg_top: null
            """
        )
        self.assertEqual(settings["ZEROES_ARE_ZEROES"], "false")
        self.assertEqual(settings["NEIGHBORS"], "14")
        self.assertEqual(settings["RESOLUTION"], "0.4")
        self.assertEqual(settings["ANALYSIS_HVG_TOP"], "")

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
        result = run_helper("export", "zeroes_are_zeroes: 'false'\n")
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
            gsm_ctrl: GSM2
            """,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("conflicting values for condition 'ctrl' in gsm", result.stderr)


if __name__ == "__main__":
    unittest.main()
