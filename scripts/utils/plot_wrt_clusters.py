#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path

import anndata as ad, anndatatools as adt
import pandas as pd

import matplotlib.pyplot as plt
from anndatatools.plotting import (
    fig,
    color
)

parser = argparse.ArgumentParser(
    prog="cluster-related plotting",
    description="""TODO""",
    usage=""""python plot_wrt_clusters.py [-h] <FILE> -o <PATH> -c <LITERAL> [<args>]"""
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file (h5ad format)"
)

parser.add_argument(
    "--csv",
    dest="csv",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="input csv file"
)

parser.add_argument(
    "-o", "--outpath",
    dest="outpath",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "-c", "--cluster",
    dest="groupby",
    type=str,
    required=True,
    nargs="+",
    metavar="LITERAL",
    help="clusters retrieving from adata.obs[`cluster`] used for cluster-related binarization"
)

parser.add_argument(
    "-l", "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used for binarization (default: use adata.X if not specified)"
)

s = """data/rna/integrated/binarization/bin.h5ad --csv data/rna/integrated/binarization/cluster_bin_macrostates.csv -o data/rna/integrated/binarization/ --cluster leiden macrostates --layer bin"""

args = parser.parse_args(s.split())

adata = ad.read_h5ad(args.infile)

df = pd.read_csv(args.csv)

df = adt.tl.anndata_to_dataframe(
    adata=adata,
    obs=["macrostates", "condition"],
    layer="bin"
)