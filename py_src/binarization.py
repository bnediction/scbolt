#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

from typing import Optional, Union
from collections import namedtuple

import os, contextlib, argparse
from pathlib import Path

import pandas as pd
import anndata as ad, anndatatools as adt

import numpy as np

from scboolseq import scBoolSeq

class Section(object):

    def __init__(
        self,
        init: int = 1,
        verbose: bool = True
    ):
        self.init = init
        self._i = init
        self._verbose = verbose
    
    def __call__(
        self,
        v: str,
        reset: bool = False
    ):
        self._i = self.init if reset else self._i
        if self._verbose is True:
            print(f"{self._i}) {v}")
        self._i+=1
        return None
    
    def reset(self):
        self._i = self.init
        return None
    
    def quiet(self):
        self._verbose = False
    
    def verbose(self):
        self._verbose = True

@contextlib.contextmanager
def disable_print():
    with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
        yield

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
        data: Union[pd.Series, pd.DataFrame],
        category: Optional[str] = None,
    ) -> Union[pd.Series, pd.DataFrame]:

        def boolean_prediction(self, zeros, ones, nans, category):
            denominator = zeros + ones
            total = denominator + nans
            if category=="Bimodal":
                if nans/total > self.__THRESHOLD.nans:
                    return float("nan")
                elif zeros/denominator > self.__THRESHOLD.bimodal:
                    return 0
                elif ones/denominator > self.__THRESHOLD.bimodal:
                    return 1
                else:
                    return float("nan")
            elif category=="ZeroInf":
                if nans/total > self.__THRESHOLD.nans:
                    return float("nan")
                elif ones/denominator > self.__THRESHOLD.zeroinf:
                    return 1
                else:
                    return 0
            elif category=="Unimodal":
                if nans/total > self.__THRESHOLD.nans:
                    return float("nan")
                elif zeros/denominator > self.__THRESHOLD.unimodal:
                    return 0
                elif ones/denominator > self.__THRESHOLD.unimodal:
                    return 1
            else:
                raise ValueError(f"Category argument must be `Bimodal`, `ZeroInf` or `Unimodal`, not `{category}`.")

        if isinstance(data, pd.Series) and category is not None:
            predict_series = pd.Series(index=data.index.get_level_values(0).unique(), name=data._name)
            if category == "Discarded":
                return predict_series
            else:
                for cluster in sorted(data.index.get_level_values(0).unique()):
                    _zeros, _ones, _nans = data[data.index.get_level_values(0) == cluster].droplevel(0)
                    _value = boolean_prediction(self, zeros=_zeros, ones=_ones, nans=_nans, category=category)
                    predict_series[cluster] = _value
                return predict_series
        elif isinstance(data, pd.DataFrame) and category is None:
            predict_df = pd.DataFrame(index=data.index.get_level_values(0).unique())
            for gene in cluster_df:
                predict_series = self.__call__(
                    data=cluster_df.loc[:,gene],
                    category=scbool.criteria_.loc[gene,"Category"]
                )
                predict_df = predict_df.join(predict_series)
            return predict_df
        else:
            raise ValueError(f"""`data` and `category` arguments must be either of types respectively {pd.Series} and {str}
            or of types respectively {pd.DataFrame} and {type(None)}, not {type(data)} and {type(category)}.""")

def obs_to_group(
    obs_df: pd.DataFrame,
    columns: list,
    group: str,
    dropna: bool = False
) -> pd.DataFrame:

    def counts(
        column_series,
        dropna
    ):
        series = column_series.value_counts(dropna=dropna).to_frame()
        series.index.set_names([column_series.keys, "value"], inplace=True)
        series.rename(columns={"count": column_series._selection}, inplace=True)
        return series

    iterables = (
        sorted(obs_df.loc[:,group].unique()),
        [float(0), float(1), np.nan]
    )
    group_df = pd.DataFrame(index=pd.MultiIndex.from_product(iterables, names=[group, "value"]))

    for column in columns:
        series = counts(obs_df.groupby(by=group)[column], dropna=dropna)
        group_df = group_df.join(series)
    
    return group_df

class arguments:
    def __init__(
        self,
        infile=Path("data/scRNA/stream/tables/stream.h5ad"),
        extension="h5ad",
        outpath=Path("data/scRNA/bool"),
        layer="log-normalize",
        hvg=True,
        verbose=True,
        groupby=["leiden"],
        nans_threshold=0.3,
        bimodal_threshold=0.6,
        zeroinf_threshold=0.3,
        unimodal_threshold=0.6
    ):
        self.infile = infile
        self.extension=extension
        self.outpath = outpath
        self.layer = layer
        self.hvg = hvg
        self.verbose=verbose
        self.groupby=groupby
        self.nans_threshold=nans_threshold
        self.bimodal_threshold=bimodal_threshold
        self.zeroinf_threshold=zeroinf_threshold
        self.unimodal_threshold=unimodal_threshold

args = arguments()

section = Section(verbose = args.verbose)

print(f"Loading data...")

adata = ad.read_h5ad(args.infile)

adata.obs_names_make_unique()
adata.var_names_make_unique()

if args.hvg is True:
    adata = adata[:,adata.var["highly_variable"]]

gene_list = list(adata.var.index)
counts_df = adt.anndata_to_dataframe(adata, layer=args.layer)

print("Data binarization...")

scbool = scBoolSeq()

section("Compute estimators")
with disable_print():
    scbool.fit(counts_df)

section("Estimate boolean values by observation")
with disable_print():
    bool_df = scbool.binarize(counts_df)

section("Count boolean values by cluster")
bool_df = pd.merge(
    bool_df,
    adata.obs.loc[:,args.groupby],
    left_index=True,
    right_index=True,
    how="inner"
)

section("Estimate boolean values by cluster")
cluster_df = obs_to_group(
    obs_df=bool_df,
    columns=gene_list,
    group="leiden",
    dropna=False
).fillna(0).astype(int)
predict = Predict(
    args.nans_threshold,
    args.bimodal_threshold,
    args.zeroinf_threshold,
    args.unimodal_threshold
)
predict_df = predict(cluster_df)

print(predict_df)