#!/usr/bin/env python

import importlib.util
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal


REPO_ROOT = Path(__file__).resolve().parents[2]
composition_path = REPO_ROOT / "scripts" / "clust" / "_composition.py"
spec = importlib.util.spec_from_file_location("composition", composition_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"could not load {composition_path}")
composition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(composition)


def test_condition_enrichment_by_label_corrects_condition_imbalance() -> None:
    obs = pd.DataFrame(
        {
            "condition": [
                "ctrl",
                "ctrl",
                "ctrl",
                "ctrl",
                "treated",
                "treated",
                "treated",
                "treated",
                "treated",
                "treated",
            ],
            "label": [
                "Rep",
                "Rep",
                "Prom",
                "Prom",
                "Rep",
                "Rep",
                "Rep",
                "Prom",
                "Prom",
                "Prom",
            ],
        }
    )

    (
        condition_by_label,
        label_by_condition,
        condition_enrichment_by_label,
    ) = composition.compute_condition_composition(
        obs,
        group_col="label",
        condition_col="condition",
    )

    expected_condition_by_label = pd.DataFrame(
        {
            "ctrl": [0.4, 0.4],
            "treated": [0.6, 0.6],
        },
        index=pd.Index(["Prom", "Rep"], name="label"),
    )
    expected_label_by_condition = pd.DataFrame(
        {
            "ctrl": [0.5, 0.5],
            "treated": [0.5, 0.5],
        },
        index=pd.Index(["Prom", "Rep"], name="label"),
    )
    expected_enrichment = pd.DataFrame(
        {
            "ctrl": [1.0, 1.0],
            "treated": [1.0, 1.0],
        },
        index=pd.Index(["Prom", "Rep"], name="label"),
    )
    expected_condition_by_label.columns.name = "condition"
    expected_label_by_condition.columns.name = "condition"
    expected_enrichment.columns.name = "condition"

    assert_frame_equal(condition_by_label, expected_condition_by_label)
    assert_frame_equal(label_by_condition, expected_label_by_condition)
    assert_frame_equal(condition_enrichment_by_label, expected_enrichment)

    rows = pd.DataFrame(
        composition.composition_rows(
            condition_by_group=condition_by_label,
            group_by_condition=label_by_condition,
            condition_enrichment_by_group=condition_enrichment_by_label,
            group_key="label",
        )
    )
    composition.check_exported_composition(rows, group_key="label")
    assert set(rows["summary"]) == {
        "condition_by_label",
        "label_by_condition",
        "condition_enrichment_by_label",
    }


def test_cluster_composition_rows_include_condition_enrichment() -> None:
    table = pd.DataFrame(
        {
            "ctrl": [0.25, 0.75],
            "treated": [0.75, 0.25],
        },
        index=pd.Index(["0", "1"], name="cluster"),
    )
    table.columns.name = "condition"
    rows = pd.DataFrame(
        composition.composition_rows(
            condition_by_group=table,
            group_by_condition=table,
            condition_enrichment_by_group=table,
            group_key="cluster",
        )
    )

    assert "condition_enrichment_by_cluster" in set(rows["summary"])
    assert {"summary", "cluster", "condition", "proportion"} == set(rows.columns)


if __name__ == "__main__":
    test_condition_enrichment_by_label_corrects_condition_imbalance()
