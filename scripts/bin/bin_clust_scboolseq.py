#!/usr/bin/env python

import argparse
import os
from collections import namedtuple
from pathlib import Path
from typing import Optional, Sequence, Union, cast

import anndata as ad
import bonesistools as bt
import numpy as np
from pandas import DataFrame, Index, MultiIndex, Series

from scbolt import cli, console, omics

omics.set_default_plot_params(bt.omics.pl)


class Predict(object):
    def __init__(
        self,
        nans_threshold: Optional[float] = None,
        bimodal_threshold: Optional[float] = None,
        zeroinf_threshold: Optional[float] = None,
        unimodal_threshold: Optional[float] = None,
    ):
        if (
            nans_threshold is None
            or bimodal_threshold is None
            or zeroinf_threshold is None
            or unimodal_threshold is None
        ):
            pass
        else:
            self.check_thresholds(
                nans_threshold, bimodal_threshold, zeroinf_threshold, unimodal_threshold
            )
            Threshold = namedtuple(
                "Constants", ["nans", "bimodal", "zeroinf", "unimodal"]
            )
            self._threshold = Threshold(
                nans_threshold, bimodal_threshold, zeroinf_threshold, unimodal_threshold
            )

    def __call__(
        self,
        data: Union[Series, DataFrame],
        category: Union[str, Series],
    ) -> Union[Series, DataFrame]:
        if isinstance(data, Series) and isinstance(category, str):
            return self._predict_series(data, category)
        if isinstance(data, DataFrame) and isinstance(category, Series):
            return self._predict_dataframe(data, category)
        raise TypeError(
            "`data` and `category` arguments must be either of types "
            f"respectively {Series} and {str}, or of types respectively "
            f"{DataFrame} and {Series}, not {type(data)} and {type(category)}."
        )

    def add(
        self,
        nans_threshold: float,
        bimodal_threshold: float,
        zeroinf_threshold: float,
        unimodal_threshold: float,
    ):
        if hasattr(self, "_threshold"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object already has attribute '_threshold'"
            )
        else:
            self.check_thresholds(
                nans_threshold, bimodal_threshold, zeroinf_threshold, unimodal_threshold
            )
            Threshold = namedtuple(
                "Constants", ["nans", "bimodal", "zeroinf", "unimodal"]
            )
            self._threshold = Threshold(
                nans_threshold, bimodal_threshold, zeroinf_threshold, unimodal_threshold
            )

    def get(self):
        if hasattr(self, "_threshold"):
            return self._threshold
        else:
            return None

    def check_thresholds(
        self,
        nans_threshold: float,
        bimodal_threshold: float,
        zeroinf_threshold: float,
        unimodal_threshold: float,
    ):
        if not isinstance(nans_threshold, float):
            raise ValueError("`nans_threshold` argument is not a float.")
        elif not isinstance(bimodal_threshold, float):
            raise ValueError("`bimodal_threshold` argument is not a float.")
        elif not isinstance(zeroinf_threshold, float):
            raise ValueError("`zeroinf_threshold` argument is not a float.")
        elif not isinstance(unimodal_threshold, float):
            raise ValueError("`unimodal_threshold` argument is not a float.")
        elif nans_threshold < 0 or nans_threshold > 1:
            raise ValueError(
                f"`nans_threshold` value ({nans_threshold}) not in range [0-1]."
            )
        elif bimodal_threshold < 0.5 or bimodal_threshold > 1:
            raise ValueError(
                f"`bimodal_threshold` value ({bimodal_threshold}) not in range [0.5-1]."
            )
        elif zeroinf_threshold < 0.5 or zeroinf_threshold > 1:
            raise ValueError(
                f"`zeroinf_threshold` value ({zeroinf_threshold}) not in range [0.5-1]."
            )
        elif unimodal_threshold < 0.5 or unimodal_threshold > 1:
            raise ValueError(
                f"`unimodal_threshold` value ({unimodal_threshold}) not in range [0.5-1]."
            )

    def _prediction_index(self, data: Union[Series, DataFrame]) -> Index:
        iterables = [
            data.index.get_level_values(level).unique()
            for level in range(data.index.nlevels - 1)
        ]
        index = MultiIndex.from_product(iterables, names=list(data.index.names)[:-1])
        if index.nlevels == 1:
            index = index.get_level_values(0)
        return index

    def _predict_series(self, data: Series, category: str) -> Series:
        index = self._prediction_index(data)
        prediction = Series(index=index, name=data._name, dtype=float)
        if category == "Discarded":
            return prediction

        for cluster in index:
            zeros, ones, nans = data.loc[cluster]
            prediction.loc[cluster] = self._predict_value(
                zeros=zeros,
                ones=ones,
                nans=nans,
                category=category,
            )
        return prediction

    def _predict_dataframe(self, data: DataFrame, category: Series) -> DataFrame:
        index = self._prediction_index(data)
        categories = np.asarray([category[gene] for gene in data.columns], dtype=object)
        valid_categories = {"Bimodal", "ZeroInf", "Unimodal", "Discarded"}
        for value in categories:
            if value not in valid_categories:
                raise ValueError(
                    "invalid parameter value for 'category': "
                    "expected 'Bimodal', 'ZeroInf' or 'Unimodal' "
                    f"but received '{value}'."
                )

        counts = data.to_numpy(copy=False)
        if counts.shape[0] != len(index) * 3:
            raise ValueError("expected three count rows per cell population")

        zeros = counts[0::3]
        ones = counts[1::3]
        nans = counts[2::3]
        not_nans = zeros + ones
        total = not_nans + nans
        prediction = np.full((len(index), data.shape[1]), np.nan, dtype=float)

        with np.errstate(divide="ignore", invalid="ignore"):
            nan_fraction = nans / total
            zero_defined_fraction = zeros / not_nans
            one_defined_fraction = ones / not_nans
            zero_total_fraction = zeros / total
            one_total_fraction = ones / total

        defined = not_nans != 0
        nans_allowed = nan_fraction <= self._threshold.nans

        for name, threshold, zero_fraction, one_fraction, allow_nans in (
            (
                "Bimodal",
                self._threshold.bimodal,
                zero_defined_fraction,
                one_defined_fraction,
                True,
            ),
            (
                "ZeroInf",
                self._threshold.zeroinf,
                zero_total_fraction,
                one_total_fraction,
                False,
            ),
            (
                "Unimodal",
                self._threshold.unimodal,
                zero_defined_fraction,
                one_defined_fraction,
                True,
            ),
        ):
            columns = categories == name
            if not columns.any():
                continue

            eligible = defined[:, columns]
            if allow_nans:
                eligible &= nans_allowed[:, columns]
            zero_votes = eligible & (zero_fraction[:, columns] > threshold)
            one_votes = eligible & ~zero_votes & (one_fraction[:, columns] > threshold)

            values = prediction[:, columns]
            values[zero_votes] = 0
            values[one_votes] = 1
            prediction[:, columns] = values

        return DataFrame(prediction, index=index, columns=data.columns)

    def _predict_value(self, zeros, ones, nans, category):
        not_nans = zeros + ones
        total = not_nans + nans
        if not_nans == 0:
            return float("nan")
        if category == "Bimodal":
            if nans / total > self._threshold.nans:
                return float("nan")
            elif zeros / not_nans > self._threshold.bimodal:
                return 0
            elif ones / not_nans > self._threshold.bimodal:
                return 1
            return float("nan")
        elif category == "ZeroInf":
            if ones / total > self._threshold.zeroinf:
                return 1
            elif zeros / total > self._threshold.zeroinf:
                return 0
            return float("nan")
        elif category == "Unimodal":
            if nans / total > self._threshold.nans:
                return float("nan")
            elif zeros / not_nans > self._threshold.unimodal:
                return 0
            elif ones / not_nans > self._threshold.unimodal:
                return 1
            return float("nan")
        raise ValueError(
            "invalid parameter value for 'category': "
            "expected 'Bimodal', 'ZeroInf' or 'Unimodal' "
            f"but received '{category}'."
        )


def count_binarized_values(
    obs_df: DataFrame,
    columns: Sequence[str],
    group: str,
    condition: Optional[str] = None,
    dropna: bool = False,
) -> DataFrame:
    group_columns = [group, condition] if condition else [group]
    group_categories = [
        sorted(obs_df.loc[:, column].cat.categories) for column in group_columns
    ]
    population_index = MultiIndex.from_product(
        group_categories,
        names=group_columns,
    )
    if len(group_columns) == 1:
        populations: Union[Index, MultiIndex] = population_index.get_level_values(0)
    else:
        populations = population_index

    index = MultiIndex.from_product(
        [*group_categories, [float(0), float(1), np.nan]],
        names=[*group_columns, "value"],
    )
    values = obs_df.loc[:, columns].to_numpy(copy=False)
    metadata = {
        column: obs_df.loc[:, column].to_numpy(copy=False) for column in group_columns
    }
    counts = np.zeros((len(populations) * 3, len(columns)), dtype=np.int64)

    for position, population in enumerate(populations):
        labels = population if isinstance(population, tuple) else (population,)
        selected = np.ones(obs_df.shape[0], dtype=bool)
        for column, label in zip(group_columns, labels):
            selected &= metadata[column] == label

        population_values = values[selected]
        row = position * 3
        counts[row] = np.count_nonzero(population_values == 0, axis=0)
        counts[row + 1] = np.count_nonzero(population_values == 1, axis=0)
        if not dropna:
            counts[row + 2] = np.count_nonzero(np.isnan(population_values), axis=0)

    return DataFrame(counts, index=index, columns=columns)


script_name = Path(__file__).name

def main() -> None:
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description=(
            "Count binarized values for each cluster and binarize clusters from "
            "binarized single-cell data using a voting rule."
        ),
        usage=f"python {script_name} [-h] <FILE> <FILE> [--counts <FILE>] --cluster <LITERAL> [<args>]",
        formatter_class=cli.HelpFormatter,
    )

    parser.add_argument(
        dest="infile",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help="input file storing binarized counts and gene distributions (format: h5ad)",
    )

    parser.add_argument(
        "outfile",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help="output file storing predicted binarized values (format: csv)",
    )

    parser.add_argument(
        "--counts",
        dest="counts",
        type=lambda x: Path(x).resolve(),
        required=False,
        default=None,
        metavar="FILE",
        help="output file storing counts of binarized values (format: csv)",
    )

    parser.add_argument(
        "--expression",
        dest="expression",
        type=str,
        required=False,
        default="bin",
        metavar="LITERAL",
        help=(
            "Expression layer to use. Expected data: binarized counts.\n" "Default: bin."
        ),
    )

    parser.add_argument(
        "--distribution",
        dest="distribution",
        type=str,
        required=False,
        default="distribution",
        metavar="LITERAL",
        help=(
            "variable name in 'adata.var' storing gene distributions (default: "
            "distribution)"
        ),
    )

    parser.add_argument(
        "--cluster",
        dest="cluster",
        type=str,
        required=True,
        metavar="LITERAL",
        help="column name in 'adata.obs' distinguishing cell populations (required)",
    )

    parser.add_argument(
        "--condition",
        dest="condition",
        type=str,
        required=False,
        default=None,
        metavar="LITERAL",
        help="column name in adata.obs distinguishing samples (default: None)",
    )

    parser.add_argument(
        "--exclude",
        dest="exclude",
        type=str,
        required=False,
        nargs="+",
        metavar="LITERAL",
        help="cluster labels to remove before cluster-level binarization",
    )

    parser.add_argument(
        "--nans-threshold",
        dest="nans_threshold",
        type=float,
        action=cli.Range,
        min=0.0,
        max=1.0,
        required=False,
        default=0.3,
        help=(
            "maximum proportion of NaN values allowed in a cluster for a gene "
            "to be binarized (not applied to zero-inflated genes, default: 0.3)"
        ),
    )

    parser.add_argument(
        "--bimodal-threshold",
        dest="bimodal_threshold",
        type=float,
        action=cli.Range,
        min=0.5,
        max=1.0,
        required=False,
        default=2 / 3,
        help=(
            "minimum proportion of zero or one values w.r.t. binarized values "
            "required for a bimodal gene to be binarized (default: 2/3)"
        ),
    )

    parser.add_argument(
        "--zeroinf-threshold",
        dest="zeroinf_threshold",
        type=float,
        action=cli.Range,
        min=0.5,
        max=1.0,
        required=False,
        default=0.5,
        help=(
            "minimum proportion of zero or one values w.r.t. binarized and NaN "
            "values required for a zero-inflated gene to be binarized (default: 0.5)"
        ),
    )

    parser.add_argument(
        "--unimodal-threshold",
        dest="unimodal_threshold",
        type=float,
        action=cli.Range,
        min=0.5,
        max=1.0,
        required=False,
        default=2 / 3,
        help=(
            "minimum proportion of zero or one values w.r.t. binarized values "
            "required for a unimodal gene to be binarized (default: 2/3)"
        ),
    )

    parser.add_argument(
        "--representation",
        dest="representation",
        type=str,
        required=False,
        default=None,
        metavar="LITERAL",
        help=(
            "Embedding representation in adata.obsm used for plotting cluster-related "
            "binarization percentages.\n"
            "Default: None."
        ),
    )

    args = parser.parse_args()

    predict = Predict(
        args.nans_threshold,
        args.bimodal_threshold,
        args.zeroinf_threshold,
        args.unimodal_threshold,
    )

    if not Path(os.path.dirname(args.outfile)).exists():
        os.makedirs(Path(os.path.dirname(args.outfile)))

    console.print_task(f"loading AnnData (file={console.format_path(args.infile)})")

    adata = ad.read_h5ad(args.infile)

    metadata = [args.cluster, args.condition] if args.condition else [args.cluster]
    convert_metadata = (
        {category: "category" for category in metadata}
        if isinstance(metadata, list)
        else "category"
    )

    console.print_info(f"converting layer '{args.expression}' into dataframe")
    cell_df = bt.omics.tl.to_dataframe(
        adata=adata, obs=metadata, layer=args.expression
    )

    console.print_task("counting binarized values (scope=cell populations)")
    cluster_counts = count_binarized_values(
        obs_df=cell_df,
        columns=list(map(str, adata.var.index)),
        group=args.cluster,
        condition=args.condition if args.condition else None,
        dropna=False,
    )

    if args.exclude:
        clusters_to_remove = set(args.exclude).intersection(
            set(cluster_counts.index.get_level_values(0).unique())
        )
        if clusters_to_remove:
            console.print_info(
                "removing clusters (clusters={0})".format(
                    "+".join(map(str, clusters_to_remove))
                )
            )
            cluster_counts = cluster_counts.drop(list(clusters_to_remove))

    console.print_task("binarizing cell populations (rules=voting)")
    cluster_bin = cast(
        DataFrame,
        predict(cluster_counts, cast(Series, adata.var[args.distribution])),
    )
    if isinstance(cluster_bin.index, MultiIndex):
        cluster_bin.index = Index(
            ["_".join(metadata) for metadata in cluster_bin.index.to_flat_index()],
            name=args.cluster,
        )

    if args.representation:
        macrostate_plot = Path(f"{os.path.dirname(args.outfile)}/{args.cluster}s.pdf")
        console.print_task(
            "plotting binarization summaries "
            f"(directory={os.path.relpath(os.path.dirname(args.outfile))})"
        )
        omics.plot_categorical_embedding(
            adata,
            obs=args.cluster,
            embedding=args.representation,
            label=console.format_embedding(args.representation),
            outfile=macrostate_plot,
        )
        pct_bin = (cluster_bin.count(axis=1) / cluster_bin.shape[1]).to_dict()
        adata.obs[f"pct_bin_{args.cluster}"] = (
            adata.obs[args.cluster].map(pct_bin).astype(float)
        )
        omics.plot_continuous_embedding(
            adata,
            obs=f"pct_bin_{args.cluster}",
            embedding=args.representation,
            label=console.format_embedding(args.representation),
            outfile=Path(f"{os.path.dirname(args.outfile)}/pct_bin_{args.cluster}.pdf"),
        )
        if args.condition:
            for condition in adata.obs[args.condition].cat.categories:
                omics.plot_continuous_embedding(
                    adata[adata.obs[args.condition] == condition],
                    obs=f"pct_bin_{args.cluster}",
                    embedding=args.representation,
                    label=console.format_embedding(args.representation),
                    outfile=Path(
                        f"{os.path.dirname(args.outfile)}/pct_bin_{args.cluster}_{condition}.pdf"
                    ),
                )

    console.print_task(f"saving binarized matrix (file={console.format_path(args.outfile)})")
    cluster_bin.to_csv(args.outfile, sep=",", index=True)

    if args.counts:
        console.print_task(
            f"saving binarized value counts (file={console.format_path(args.counts)})"
        )
        cluster_counts.to_csv(args.counts, sep=",", index=True)


if __name__ == "__main__":
    main()
