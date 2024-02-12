#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

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

def obs_to_group(
    obs_df: pd.DataFrame,
    columns: list,
    group: str,
    dropna: bool = False
):

    def counts(
        column_series,
        dropna
    ):
        series = column_series.value_counts(dropna=dropna).to_frame()
        series.index.set_names([column_series.keys, "value"], inplace=True)
        series.rename(columns={"count": column_series._selection}, inplace=True)
        return series

    iterables = (
        sorted(obs_df.loc[:,group.unique()]),
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
        groupby=["leiden"]
    ):
        self.infile = infile
        self.extension=extension
        self.outpath = outpath
        self.layer = layer
        self.hvg = hvg
        self.verbose=verbose
        self.groupby=groupby

args = arguments()

section = Section(verbose = args.verbose)

print(f"Loading data...")

adata = ad.read_h5ad(args.infile)

adata.obs_names_make_unique()
adata.var_names_make_unique()

gene_list = list(adata.var.index)

if args.hvg is True:
    adata = adata[:,adata.var["highly_variable"]]

counts_df = adt.anndata_to_dataframe(adata, layer=args.layer)

print("Data binarization...")

scbool = scBoolSeq()

section("compute estimators")
with disable_print():
    scbool.fit(counts_df)

section("estimate boolean values by observation")
with disable_print():
    bool_df = scbool.binarize(counts_df)

section("estimate boolean values by cluster")
bool_df = pd.merge(
    bool_df,
    adata.obs.loc[:,args.groupby],
    left_index=True,
    right_index=True,
    how="inner"
)

leiden_df = obs_to_group(
    obs_df=bool_df,
    columns=gene_list,
    group="leiden",
    dropna=False
).fillna(0).astype(int)

args.pct = 0.3
