#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

from typing import Optional, Union, List
from collections import namedtuple

import os, std
import argparse, cli
from pathlib import Path

from pandas import DataFrame, Series, MultiIndex
import anndata as ad
import bonesistools as bt

import numpy as np

bt.sct.pl.set_default_params()


class Predict(object):

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
        else:
            pass

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
            self.__THRESHOLD = Threshold(
                nans_threshold, bimodal_threshold, zeroinf_threshold, unimodal_threshold
            )

    def add(
        self,
        nans_threshold: float,
        bimodal_threshold: float,
        zeroinf_threshold: float,
        unimodal_threshold: float,
    ):
        if hasattr(self, f"_{self.__class__.__name__}__THRESHOLD"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object already attribute '_{self.__class__.__name__}__THRESHOLD'"
            )
        else:
            self.check_thresholds(
                nans_threshold, bimodal_threshold, zeroinf_threshold, unimodal_threshold
            )
            Threshold = namedtuple(
                "Constants", ["nans", "bimodal", "zeroinf", "unimodal"]
            )
            self.__THRESHOLD = Threshold(
                nans_threshold, bimodal_threshold, zeroinf_threshold, unimodal_threshold
            )

    def get(self):
        if hasattr(self, f"_{self.__class__.__name__}__THRESHOLD"):
            return self.__THRESHOLD
        else:
            return None

    def __call__(
        self,
        data: Union[Series, DataFrame],
        category: Union[str, Series],
    ) -> Union[Series, DataFrame]:

        def boolean_prediction(self, zeros, ones, nans, category):
            not_nans = zeros + ones
            total = not_nans + nans
            if not_nans == 0:
                return float("nan")
            if category == "Bimodal":
                if nans / total > self.__THRESHOLD.nans:
                    return float("nan")
                elif zeros / not_nans > self.__THRESHOLD.bimodal:
                    return 0
                elif ones / not_nans > self.__THRESHOLD.bimodal:
                    return 1
                else:
                    return float("nan")
            elif category == "ZeroInf":
                if ones / total > self.__THRESHOLD.zeroinf:
                    return 1
                elif zeros / total > self.__THRESHOLD.zeroinf:
                    return 0
                else:
                    return float("nan")
            elif category == "Unimodal":
                if nans / total > self.__THRESHOLD.nans:
                    return float("nan")
                elif zeros / not_nans > self.__THRESHOLD.unimodal:
                    return 0
                elif ones / not_nans > self.__THRESHOLD.unimodal:
                    return 1
            else:
                raise ValueError(
                    f"invalid parameter value for 'category': expected 'Bimodal', 'ZeroInf' or 'Unimodal' but received '{category}'."
                )

        _iterable = (
            data.index.get_level_values(level).unique()
            for level in range(data.index.nlevels - 1)
        )
        _names = list(data.index.names)[:-1]
        index = MultiIndex.from_product(_iterable, names=_names)
        if index.nlevels == 1:
            index = index.get_level_values(0)

        if isinstance(data, Series) and isinstance(category, str):
            predict_series = Series(index=index, name=data._name)
            if category == "Discarded":
                return predict_series
            else:
                for cluster in index:
                    _zeros, _ones, _nans = data.loc[cluster]
                    _value = boolean_prediction(
                        self, zeros=_zeros, ones=_ones, nans=_nans, category=category
                    )
                    predict_series[cluster] = _value
                return predict_series
        elif isinstance(data, DataFrame) and isinstance(category, Series):
            cluster_binf = DataFrame(index=index)
            for gene in data:
                predict_series = self.__call__(
                    data=data.loc[:, gene], category=category[gene]
                )
                cluster_binf = cluster_binf.join(predict_series)
            return cluster_binf
        else:
            raise TypeError(
                f"""`data` and `category` arguments must be either of types respectively {Series} and {str}
            or of types respectively {DataFrame} and {Series}, not {type(data)} and {type(category)}."""
            )


def count_binarized_values(
    obs_df: DataFrame,
    columns: List,
    group: str,
    condition: Optional[str] = None,
    dropna: bool = False,
) -> DataFrame:

    def counts(column_series, dropna):
        series = column_series.value_counts(dropna=dropna).to_frame()
        keys = (
            [*column_series.keys, "value"]
            if isinstance(column_series.keys, list)
            else [column_series.keys, "value"]
        )
        series.index.set_names(keys, inplace=True)
        series.rename(columns={"count": column_series._selection}, inplace=True)
        return series

    if condition:
        iterables = (
            sorted(obs_df.loc[:, group].cat.categories),
            sorted(obs_df.loc[:, condition].cat.categories),
            [float(0), float(1), np.nan],
        )
        names = [group, condition, "value"]
    else:
        iterables = (
            sorted(obs_df.loc[:, group].cat.categories),
            [float(0), float(1), np.nan],
        )
        names = [group, "value"]

    group_df = DataFrame(index=MultiIndex.from_product(iterables, names=names))

    for column in columns:
        series = counts(
            obs_df.groupby(by=group if condition is None else [group, condition])[
                column
            ],
            dropna=dropna,
        )
        group_df = group_df.join(series)

    return group_df.fillna(0).astype(int)


parser = argparse.ArgumentParser(
    prog="bin_clusters_scboolseq",
    description="""
    count binarized values for each cluster and binarize clusters from binarized single cell data using voting rule.
    """,
    usage=""""python bin_clusters_scboolseq.py <FILE...> <FILE> [--counts <FILE>] --cluster <LITERAL> [<args>]""",
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing binarized counts and gene distribution-related variable (format: h5ad)",
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
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default="bin",
    metavar="LITERAL",
    help="layer used corresponding to binarized counts (default: bin)",
)

parser.add_argument(
    "--distribution",
    dest="distribution",
    type=str,
    required=False,
    default="distribution",
    metavar="LITERAL",
    help="variable name in 'adata.var' storing gene distributions (default: distribution)",
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
    help="column name such as adata.obs[`LITERAL`] distinguishes samples (default: None)",
)

parser.add_argument(
    "--exclude",
    dest="exclude",
    type=str,
    required=False,
    nargs="+",
    metavar="LITERAL",
    help="cluster names in adata.obs['cluster'] to remove for cluster-related binarization",
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
    help="maximum proportion of nan-values in a cluster required for a gene to be binarized (not applied to zero-inflated genes, default: 0.3)",
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
    help="minimum proportion of zero- or one-values w.r.t binarized values in a cluster required for a bimodal gene to be binarized (default: 2/3)",
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
    help="minimum proportion of zero- or one-values w.r.t binarized and nan values in a cluster required for a zero-inflated gene to be binarized (default: 0.5)",
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
    help="minimum proportion of zero- or one-values w.r.t binarized values in a cluster required for a unimodal gene to be binarized (default: 2/3)",
)

parser.add_argument(
    "--use-rep",
    dest="use_rep",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="embedding projection in adata.obsm used for plotting percentage of cluster-related binarization (default: None)",
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

std.print_task(f"loading data from {str(args.infile)}")

adata = ad.read_h5ad(args.infile)

metadata = [args.cluster, args.condition] if args.condition else [args.cluster]
convert_metadata = (
    {category: "category" for category in metadata}
    if isinstance(metadata, list)
    else "category"
)

std.print_info(f"converting layer '{args.layer}' into dataframe")
cell_df = bt.sct.tl.anndata_to_dataframe(adata=adata, obs=metadata, layer=args.layer)

std.print_task("counting binarized values for each cell population")
cluster_counts = count_binarized_values(
    obs_df=cell_df,
    columns=adata.var.index,
    group=args.cluster,
    condition=args.condition if args.condition else None,
    dropna=False,
)

if args.exclude:
    clusters_to_remove = set(args.exclude).intersection(
        set(cluster_counts.index.get_level_values(0).unique())
    )
    if clusters_to_remove:
        std.print_info(
            "removing the following cluster(s): {0}".format(
                ", ".join(f"'{cluster}'" for cluster in clusters_to_remove)
            )
        )
        cluster_counts = cluster_counts.drop(clusters_to_remove)

std.print_task("binarizing cell populations with respect to voting rules")
cluster_bin = predict(cluster_counts, adata.var[args.distribution])
if isinstance(cluster_bin.index, MultiIndex):
    cluster_bin.index = [
        "_".join(metadata) for metadata in cluster_bin.index.to_flat_index()
    ]
    cluster_bin.index.name = args.cluster

if args.use_rep:
    embedding_label = (
        args.use_rep[2:].lower()
        if args.use_rep.startswith("X_")
        else args.use_rep.lower()
    )
    std.print_task(f"plotting binarization summaries in {os.path.relpath(os.path.dirname(args.outfile))}")
    pct_bin = (cluster_bin.count(axis=1) / cluster_bin.shape[1]).to_dict()
    adata.obs[f"pct_bin_{args.cluster}"] = adata.obs[args.cluster].map(pct_bin)
    bt.sct.pl.embedding_plot(
        adata,
        obs=f"pct_bin_{args.cluster}",
        use_rep=args.use_rep,
        xlabel=r"$\mathrm{{{}_{{1}}}}$".format(embedding_label),
        ylabel=r"$\mathrm{{{}_{{2}}}}$".format(embedding_label),
        zlabel=r"$\mathrm{{{}_{{3}}}}$".format(embedding_label),
        figwidth=6,
        s=4,
        alpha=1,
        add_legend=True,
        lgd_params={
            "title": "pct bin",
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": bt.sct.pl.get_color("black"),
            "shadow": False,
        },
        n_components=3 if adata.obsm[args.use_rep].shape[1] > 2 else 2,
        background_visible=False,
        outfile=Path(f"{os.path.dirname(args.outfile)}/pct_bin_{args.cluster}.pdf"),
    )
    if args.condition:
        for condition in adata.obs[args.condition].cat.categories:
            bt.sct.pl.embedding_plot(
                adata[adata.obs[args.condition] == condition],
                obs=f"pct_bin_{args.cluster}",
                obsm=args.use_rep,
                xlabel=r"$\mathrm{{{}_{{1}}}}$".format(embedding_label),
                ylabel=r"$\mathrm{{{}_{{2}}}}$".format(embedding_label),
                zlabel=r"$\mathrm{{{}_{{3}}}}$".format(embedding_label),
                figwidth=6,
                s=4,
                alpha=1,
                add_legend=True,
                lgd_params={
                    "title": "pct bin",
                    "ncol": 1,
                    "markerscale": 5,
                    "frameon": True,
                    "edgecolor": bt.sct.pl.get_color("black"),
                    "shadow": False,
                },
                n_components=3 if adata.obsm[args.use_rep].shape[1] > 2 else 2,
                background_visible=False,
                outfile=Path(
                    f"{os.path.dirname(args.outfile)}/pct_bin_{args.cluster}_{condition}.pdf"
                ),
            )

std.print_task(f"saving predicted binarized values in {str(args.outfile)}")
cluster_bin.to_csv(args.outfile, sep=",", index=True)

if args.counts:
    std.print_task(f"saving counts of binarized values in {str(args.counts)}")
    cluster_counts.to_csv(args.counts, sep=",", index=True)
