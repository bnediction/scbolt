#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

from typing import Optional, Union, List
from collections import namedtuple
from bonesistools.utils.argtype import Range
from bonesistools.utils.stdout import (
    print_task,
    print_info
)

import os, argparse
from pathlib import Path

from pandas import (
    DataFrame,
    Series,
    MultiIndex
)
import anndata as ad, anndatatools as adt

import numpy as np

import matplotlib.pyplot as plt
from anndatatools.plotting import color

class Predict(object):

    def check_thresholds(
        self,
        nans_threshold: float,
        bimodal_threshold: float,
        zeroinf_threshold: float,
        unimodal_threshold: float
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
            raise ValueError(f"`nans_threshold` value ({nans_threshold}) not in range [0-1].")
        elif bimodal_threshold < 0.5 or bimodal_threshold > 1:
            raise ValueError(f"`bimodal_threshold` value ({bimodal_threshold}) not in range [0.5-1].")
        elif zeroinf_threshold < 0 or zeroinf_threshold > 0.5:
            raise ValueError(f"`zeroinf_threshold` value ({zeroinf_threshold}) not in range [0-0.5].")
        elif unimodal_threshold < 0.5 or unimodal_threshold > 1:
            raise ValueError(f"`unimodal_threshold` value ({unimodal_threshold}) not in range [0.5-1].")
        else:
            pass

    def __init__(
        self,
        nans_threshold: Optional[float] = None,
        bimodal_threshold: Optional[float] = None,
        zeroinf_threshold: Optional[float] = None,
        unimodal_threshold: Optional[float] = None
    ):
        if nans_threshold is None or bimodal_threshold is None or zeroinf_threshold is None or unimodal_threshold is None:
            pass
        else:
            self.check_thresholds(nans_threshold, bimodal_threshold, zeroinf_threshold, unimodal_threshold)
            Threshold = namedtuple("Constants", ["nans", "bimodal", "zeroinf", "unimodal"])
            self.__THRESHOLD = Threshold(
                nans_threshold,
                bimodal_threshold,
                zeroinf_threshold,
                unimodal_threshold
            )
    
    def add(
        self,
        nans_threshold: float,
        bimodal_threshold: float,
        zeroinf_threshold: float,
        unimodal_threshold: float
    ):
        if hasattr(self, f"_{self.__class__.__name__}__THRESHOLD"):
            raise AttributeError(f"'{self.__class__.__name__}' object already attribute '_{self.__class__.__name__}__THRESHOLD'")
        else:
            self.check_thresholds(nans_threshold, bimodal_threshold, zeroinf_threshold, unimodal_threshold)
            Threshold = namedtuple("Constants", ["nans", "bimodal", "zeroinf", "unimodal"])
            self.__THRESHOLD = Threshold(
                nans_threshold,
                bimodal_threshold,
                zeroinf_threshold,
                unimodal_threshold
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
            if category=="Bimodal":
                if nans/total > self.__THRESHOLD.nans:
                    return float("nan")
                elif zeros/not_nans > self.__THRESHOLD.bimodal:
                    return 0
                elif ones/not_nans > self.__THRESHOLD.bimodal:
                    return 1
                else:
                    return float("nan")
            elif category=="ZeroInf":
                if nans/total > self.__THRESHOLD.nans:
                    return float("nan")
                elif ones/not_nans > self.__THRESHOLD.zeroinf:
                    return 1
                elif zeros/not_nans > self.__THRESHOLD.zeroinf:
                    return 0
                else:
                    return float("nan")
            elif category=="Unimodal":
                if nans/total > self.__THRESHOLD.nans:
                    return float("nan")
                elif zeros/not_nans > self.__THRESHOLD.unimodal:
                    return 0
                elif ones/not_nans > self.__THRESHOLD.unimodal:
                    return 1
            else:
                raise ValueError(f"Category argument must be `Bimodal`, `ZeroInf` or `Unimodal`, not `{category}`.")
        
        _iterable = (data.index.get_level_values(level).unique() for level in range(data.index.nlevels - 1))
        _names = list(data.index.names)[:-1]
        index = MultiIndex.from_product(_iterable, names=_names)
        if index.nlevels == 1:
            index = index.get_level_values(0)

        if isinstance(data, Series) and isinstance(category,str):
            predict_series = Series(index=index, name=data._name)
            if category == "Discarded":
                return predict_series
            else:
                for cluster in index:
                    _zeros, _ones, _nans = data.loc[cluster]
                    _value = boolean_prediction(self, zeros=_zeros, ones=_ones, nans=_nans, category=category)
                    predict_series[cluster] = _value
                return predict_series
        elif isinstance(data, DataFrame) and isinstance(category, Series):
            predict_df = DataFrame(index=index)
            for gene in data:
                predict_series = self.__call__(
                    data=data.loc[:,gene],
                    category=category[gene]
                )
                predict_df = predict_df.join(predict_series)
            return predict_df
        else:
            raise TypeError(f"""`data` and `category` arguments must be either of types respectively {Series} and {str}
            or of types respectively {DataFrame} and {Series}, not {type(data)} and {type(category)}.""")

def cell_to_cluster_binarization(
    obs_df: DataFrame,
    columns: List,
    group: str,
    condition: Optional[str] = None,
    dropna: bool = False
) -> DataFrame:

    def counts(
        column_series,
        dropna
    ):
        series = column_series.value_counts(dropna=dropna).to_frame()
        keys = [*column_series.keys, "value"] if isinstance(column_series.keys, list) else [column_series.keys, "value"]
        series.index.set_names(keys, inplace=True)
        series.rename(columns={"count": column_series._selection}, inplace=True)
        return series

    if condition:
        iterables = (
            sorted(obs_df.loc[:,group].cat.categories),
            sorted(obs_df.loc[:,condition].cat.categories),
            [float(0), float(1), np.nan]
        )
        names = [group, condition, "value"]
    else:
        iterables = (
            sorted(obs_df.loc[:,group].cat.categories),
            [float(0), float(1), np.nan]
        )
        names = [group,"value"]
    
    group_df = DataFrame(index=MultiIndex.from_product(iterables, names=names))

    for column in columns:
        series = counts(obs_df.groupby(by=group if condition is None else [group, condition])[column], dropna=dropna)
        group_df = group_df.join(series)

    return group_df.fillna(0).astype(int)

parser = argparse.ArgumentParser(
    prog="cluster binarization",
    description="""compute cluster-related binarization from single-cell sequencing data using voting rule""",
    usage=""""python macrostate_binarization.py [-h] <FILE...> -o <PATH> -c <LITERAL> [<args>]"""
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file with binarized layer (h5ad format)"
)

parser.add_argument(
    dest="outpath",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default="bin",
    metavar="LITERAL",
    help="layer storing binarized counts (default: bin)"
)

parser.add_argument(
    "--cluster",
    dest="groupby",
    type=str,
    required=True,
    nargs="+",
    metavar="LITERAL",
    help="clusters retrieving from adata.obs[`cluster`] used for cluster-related binarization"
)

parser.add_argument(
    "--condition",
    dest="condition",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="column name such as adata.obs[`LITERAL`] distinguishes samples (default: None)"
)

parser.add_argument(
    "-e", "--exclude",
    dest="exclude",
    type=str,
    required=False,
    nargs="+",
    metavar="LITERAL",
    help="cluster names to remove for cluster-related binarization"
)

parser.add_argument(
    "-n", "--nans-threshold",
    dest="nans_threshold",
    type=float,
    action=Range,
    min=0.0,
    max=1.0,
    required=False,
    default=0.3,
    help="""set binarized gene value of a cluster to nan if the proportion of nan values
    in the cluster is above `nans_threshold` (default: 0.3)"""
)

parser.add_argument(
    "-b", "--bimodal-threshold",
    dest="bimodal_threshold",
    type=float,
    action=Range,
    min=0.5,
    max=1.0,
    required=False,
    default=2/3,
    help="""for a bimodal gene, set binarized gene value of a cluster to 0 (resp. 1)
    if the proportion of zero-values (resp. one-values) in the cluster is above `bimodal_threshold`
    with respect to binarized values (default: 2/3)"""
)

parser.add_argument(
    "-z", "--zeroinf-threshold",
    dest="zeroinf_threshold",
    type=float,
    action=Range,
    min=0.5,
    max=1.0,
    required=False,
    default=0.5,
    help="""for a zero-inflated gene, set binarized gene value of a cluster to 1
    if the proportion of one-values in the cluster is above `zeroinf_threshold`,
    otherwise 0 (default: 0.5)"""
)

parser.add_argument(
    "-u", "--unimodal-threshold",
    dest="unimodal_threshold",
    type=float,
    action=Range,
    min=0.5,
    max=1.0,
    required=False,
    default=2/3,
    help="""for a unimodal gene, set binarized gene value of a cluster to 0 (resp. 1)
    if the proportion of zero-values (resp. one-values) in the cluster is above `unimodal_threshold`
    with respect to binarized values (default: 2/3)"""
)

parser.add_argument(
    "--plot-3d",
    dest="plot_3d",
    required=False,
    action="store_true",
    help="plot figures in three dimensions"
)

args = parser.parse_args()

predict = Predict(
    args.nans_threshold,
    args.bimodal_threshold,
    args.zeroinf_threshold,
    args.unimodal_threshold
)

if not args.outpath.exists():
    os.makedirs(args.outpath)

print_task("data loading")

adata = ad.read_h5ad(args.infile)

print_task("cluster binarization")

cluster_d = dict()
predict_d = dict()
for _group in args.groupby:
    print_info(f"binarizing cluster `{_group}`")
    metadata = [_group, args.condition] if args.condition else [_group]
    convert_metadata = {category: "category" for category in metadata} if isinstance(metadata,list) else "category"
    _cell_df = adt.tl.anndata_to_dataframe(
        adata=adata,
        obs=metadata,
        layer="bin"
    )
    cluster_d[_group] = cell_to_cluster_binarization(
        obs_df=_cell_df,
        columns=adata.var.index,
        group=_group,
        condition = args.condition if args.condition else None,
        dropna=False
    )
    if args.exclude:
        _index_label_to_drop = list()
        for _index_label in args.exclude:
            if _index_label in cluster_d[_group].index.get_level_values(0).unique():
                _index_label_to_drop.append(_index_label)
        if _index_label_to_drop:
            cluster_d[_group] = cluster_d[_group].drop(_index_label_to_drop)
        del _index_label_to_drop, _index_label
    predict_d[_group] = predict(cluster_d[_group], adata.var["distribution"])
    if isinstance(predict_d[_group].index, MultiIndex):
        predict_d[_group].index = ["_".join(metadata) for metadata in predict_d[_group].index.to_flat_index()]
        predict_d[_group].index.name = _group

if args.condition:
    for _group in args.groupby:
        print_info(f"renaming categories for `{_group}`")
        adata.obs[_group] = (adata.obs[_group].astype(str) + "_" + adata.obs[args.condition].astype(str)).astype("category")
        _nans_cat = {"nan_" + condition for condition in adata.obs[args.condition].cat.categories}
        _nans_cat = [x for x in _nans_cat if x in set(adata.obs[_group].cat.categories)]
        adata.obs[_group] = adata.obs[_group].cat.remove_categories(_nans_cat)

print_task("data saving")

adata.write_h5ad(filename=f"{args.outpath}/bin_clusters.h5ad", compression="gzip")
for _group in args.groupby:
    cluster_d[_group].transpose().to_csv(f"{args.outpath}/counting_bin_{_group}.csv", sep=",", index=True)
    predict_d[_group].transpose().to_csv(f"{args.outpath}/bin_{_group}.csv", sep=",", index=True)

print_task("plotting")
for _group in args.groupby:
    print_info(f"checking cluster homogeneity for `{_group}`")
    pct_binarized = (predict_d[_group].count(axis=1) / predict_d[_group].shape[1]).to_dict()
    adata.obs[f"pct_bin_{_group}"] = adata.obs[_group].map(pct_binarized)
    fig, _ = adt.pl.embedding_plot(
        adata,
        obs=f"pct_bin_{_group}",
        obsm="X_umap",
        xlabel=r"$\mathrm{UMAP_{1}}$",
        ylabel=r"$\mathrm{UMAP_{2}}$",
        zlabel=r"$\mathrm{UMAP_{3}}$",
        add_legend=True,
        figwidth=6,
        s=4,
        alpha=1,
        lgd_params={
            "title":"pct bin",
            "ncol":1,
            "markerscale":5,
            "frameon":True,
            "edgecolor":color.black,
            "shadow":False
        },
        n_components = 3 if adata.obsm["X_umap"].shape[1] > 2 and args.plot_3d is True else 2,
        background_visible=False
    )
    plt.savefig(Path(f"{args.outpath}/pct_bin_{_group}.pdf"))
    if args.condition:
        for _condition in adata.obs[args.condition].cat.categories:
            fig, _ = adt.pl.embedding_plot(
                adata[adata.obs[args.condition]==_condition],
                obs=f"pct_bin_{_group}",
                obsm="X_umap",
                xlabel=r"$\mathrm{UMAP_{1}}$",
                ylabel=r"$\mathrm{UMAP_{2}}$",
                zlabel=r"$\mathrm{UMAP_{3}}$",
                add_legend=True,
                figwidth=6,
                s=4,
                alpha=1,
                lgd_params={
                    "title":"pct bin",
                    "ncol":1,
                    "markerscale":5,
                    "frameon":True,
                    "edgecolor":color.black,
                    "shadow":False
                },
                n_components = 3 if adata.obsm["X_umap"].shape[1] > 2 and args.plot_3d is True else 2,
                background_visible=False
            )
            plt.savefig(Path(f"{args.outpath}/pct_bin_{_group}_cond_{_condition}.pdf"))
