#!/usr/bin/env python

import pandas as pd


def check_proportion_sums(
    table: pd.DataFrame,
    name: str,
    axis: int,
    tolerance: float = 1e-8,
) -> None:
    sums = table.sum(axis=axis)
    invalid = sums[(sums - 1.0).abs() > tolerance]
    if not invalid.empty:
        details = ", ".join(f"{index}={value:.6g}" for index, value in invalid.items())
        raise ValueError(f"invalid composition proportions for {name}: {details}")


def compute_condition_composition(
    obs: pd.DataFrame,
    group_col: str,
    condition_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    counts = pd.crosstab(obs[group_col], obs[condition_col])
    counts = counts.reindex(sorted(counts.columns), axis=1)

    condition_by_group = counts.div(counts.sum(axis=1), axis=0)
    condition_by_group = condition_by_group.reindex(
        sorted(condition_by_group.columns),
        axis=1,
    )

    group_by_condition = pd.crosstab(
        obs[condition_col],
        obs[group_col],
        normalize="index",
    ).T
    group_by_condition = group_by_condition.reindex(condition_by_group.index, axis=0)
    group_by_condition = group_by_condition.reindex(
        condition_by_group.columns,
        axis=1,
    )

    condition_global = obs[condition_col].value_counts(normalize=True)
    condition_global = condition_global.reindex(condition_by_group.columns)
    condition_enrichment_by_group = condition_by_group.div(condition_global, axis=1)

    check_proportion_sums(
        condition_by_group,
        name=f"condition_by_{group_col}",
        axis=1,
    )
    check_proportion_sums(
        group_by_condition,
        name=f"{group_col}_by_condition",
        axis=0,
    )

    return condition_by_group, group_by_condition, condition_enrichment_by_group


def composition_rows(
    condition_by_group: pd.DataFrame,
    group_by_condition: pd.DataFrame,
    condition_enrichment_by_group: pd.DataFrame,
    group_key: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    summaries = {
        f"condition_by_{group_key}": condition_by_group,
        f"{group_key}_by_condition": group_by_condition,
        f"condition_enrichment_by_{group_key}": condition_enrichment_by_group,
    }
    for summary, table in summaries.items():
        for group in table.index:
            for condition in table.columns:
                rows.append(
                    {
                        "summary": summary,
                        group_key: group,
                        "condition": condition,
                        "proportion": float(table.loc[group, condition]),
                    }
                )
    return rows


def check_exported_composition(
    composition: pd.DataFrame,
    group_key: str,
) -> None:
    checks = {
        f"condition_by_{group_key}": group_key,
        f"{group_key}_by_condition": "condition",
    }
    for summary, groupby in checks.items():
        subset = composition.loc[composition["summary"] == summary]
        sums = subset.groupby(groupby, observed=False)["proportion"].sum()
        invalid = sums[(sums - 1.0).abs() > 1e-8]
        if not invalid.empty:
            details = ", ".join(
                f"{index}={value:.6g}" for index, value in invalid.items()
            )
            raise ValueError(
                f"invalid exported composition proportions for {summary}: {details}"
            )
