"""Integrity tests for the versioned quickstart fixtures."""

from __future__ import annotations

import csv
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
QUICKSTART = REPO / "quickstart"
CONFIG_HELPER = REPO / "scripts" / "utils" / "project_config.py"

FEEDBACK_NODES = {
    "Ar",
    "Bach2",
    "Cebpa",
    "Ctcf",
    "E2f2",
    "E2f4",
    "Egr1",
    "Epas1",
    "Esr1",
    "Ets1",
    "Foxm1",
    "Gata2",
    "Irf2",
    "Klf5",
    "Lef1",
    "Lyl1",
    "Myb",
    "Myc",
    "Nfe2l2",
    "Nfkb1",
    "Nr1h3",
    "Pou2f1",
    "Pou2f2",
    "Pou5f1",
    "Pparg",
    "Rara",
    "Runx3",
    "Sp1",
    "Srebf1",
    "Tal1",
    "Tcf3",
    "Tcf4",
    "Tfap2a",
    "Tfap2c",
    "Trp53",
    "Yy1",
    "Zeb2",
}


class QuickstartTests(unittest.TestCase):
    def test_configuration_is_valid_and_uses_fast_static_inputs(self) -> None:
        self.assertEqual(
            (QUICKSTART / ".scbolt").read_text(encoding="utf-8"),
            "CONFIG=scbolt.yml\n",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(CONFIG_HELPER),
                "export",
                str(QUICKSTART / "scbolt.yml"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = dict(
            line.split("\t", 1) for line in result.stdout.splitlines()
        )
        self.assertEqual(settings["BINARIZATION_FILE"], "data/mstates_bin.csv")
        self.assertEqual(settings["PRIOR_KNOWLEDGE"], "data/interactions.csv")
        self.assertEqual(settings["STRONG_CONSTANTS_SCOPE"], "none")
        self.assertEqual(settings["INFER_LIMIT"], "10")
        self.assertEqual(settings["CLINGO_MODE_RELAXED"], "optN")
        self.assertEqual(settings["CLINGO_STRATEGY_RELAXED"], "usc")
        self.assertEqual(settings["CLINGO_MODE_SEED"], "opt")
        self.assertEqual(settings["CLINGO_STRATEGY_SEED"], "bb,inc")
        self.assertEqual(settings["TIMEOUT_RELAXED"], "2m")
        self.assertEqual(settings["TIMEOUT_SEED"], "5m")
        self.assertEqual(settings["CLAUSE_CONTINUATION_SOFT"], "false")
        self.assertEqual(settings["DOMAIN_CONTINUATION_SOFT"], "false")
        self.assertEqual(settings["CLAUSE_CONTINUATION_RELAXED"], "false")
        self.assertEqual(settings["DOMAIN_CONTINUATION_RELAXED"], "false")
        self.assertEqual(settings["CLAUSE_CONTINUATION_SEED"], "false")
        self.assertEqual(settings["DOMAIN_CONTINUATION_SEED"], "false")

    def test_boolean_states_and_interactions_share_the_80_node_domain(self) -> None:
        with (QUICKSTART / "data" / "mstates_bin.csv").open(
            newline="", encoding="utf-8"
        ) as stream:
            state_reader = csv.DictReader(stream)
            states = list(state_reader)
        fieldnames = state_reader.fieldnames
        self.assertIsNotNone(fieldnames)
        assert fieldnames is not None
        state_nodes = set(fieldnames[1:])
        self.assertEqual(len(state_nodes), 80)
        self.assertEqual(
            [state["macrostate"] for state in states],
            ["S0", "S1", "S2", "S3", "S4", "S5"],
        )
        self.assertTrue(
            all(
                value in {"", "0.0", "1.0"}
                for state in states
                for key, value in state.items()
                if key != "macrostate"
            )
        )

        with (QUICKSTART / "data" / "interactions.csv").open(
            newline="", encoding="utf-8"
        ) as stream:
            interaction_reader = csv.DictReader(stream)
            interactions = list(interaction_reader)
        self.assertEqual(
            interaction_reader.fieldnames,
            ["source", "target", "sign"],
        )
        edges = {
            (edge["source"], edge["target"], edge["sign"])
            for edge in interactions
        }
        interaction_nodes = {
            node
            for edge in interactions
            for node in (edge["source"], edge["target"])
        }
        self.assertEqual(len(interactions), 139)
        self.assertEqual(len(edges), 139)
        self.assertEqual(interaction_nodes, state_nodes)
        self.assertEqual({edge["sign"] for edge in interactions}, {"-1", "1"})

    def test_specification_prioritizes_the_ensemble_feedback_nodes(self) -> None:
        specification = yaml.safe_load(
            (QUICKSTART / "spec.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(set(specification["important-nodes"]), FEEDBACK_NODES)
        self.assertEqual(len(specification["constraints"]), 14)
        self.assertEqual(specification["mandatory-nodes"], [])
        self.assertEqual(specification["forbidden-nodes"], [])


if __name__ == "__main__":
    unittest.main()
