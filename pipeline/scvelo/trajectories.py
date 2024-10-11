#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path

import re

import pandas as pd
import anndatatools as adt, scvelo as scv

import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(
    prog="scvelo of sc-RNAseq data",
    description="""From one-condition sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    perform scvelo analysis.""",
    usage="python scvelo.py <FILE> <PATH> [<args>]"
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="file in h5ad format"
)

parser.add_argument(
    "outpath",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=False,
    metavar="LITERAL",
    help="column name such as adata.obs[`LITERAL`] distinguishes cluster"
)

parser.add_argument(
    "-k", "--k-neighbors",
    dest="k_neighbors",
    type=int,
    required=False,
    default=20,
    metavar="PATH",
    help="number of closest neighbors computed when computing KNN graph (default: 20)"
)

parser.add_argument(
    "-p", "--dim-pca",
    dest="dim_pca",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of principal components (default: 50)"
)

parser.add_argument(
    "-m", "--mode",
    dest="mode",
    type=str,
    required=False,
    choices=["deterministic", "stochastic", "dynamical"],
    default="stochastic",
    metavar="[deterministic | stochastic | dynamical]",
    help="mode used to estimate the steady-state model (default: stochastic)"
)

s = """data/rna/ctrl/cluster/tables/counts_labels.h5ad data/rna/ctrl/scvelo --cluster leiden --k-neighbors 30 --dim-pca 30 --mode stochastic"""

args = parser.parse_args(s.split())

if not args.outpath.exists():
    os.makedirs(args.outpath)

print(f"Loading data...")

adata = scv.read(args.infile, cache=True)
adata2 = scv.datasets.pancreas()

# scv.set_figure_params()
# adt.pl.set_default()

adata.obs["clusters"] = adata.obs[args.cluster]
# n_clusters = len(adata.obs["clusters"].cat.categories)
import numpy as np

adata.uns["colors"] = np.array([adt.pl.rgb2hex(adt.pl.COLORS[idx]) for idx, _ in enumerate (adata.obs["clusters"].cat.categories)])
color_map = {cluster: adt.pl.rgb2hex(adt.pl.COLORS[idx]) for idx, cluster in enumerate(adata.obs["clusters"].cat.categories)}
# adata.obs["cluster_colors"] = adata.obs["clusters"].map(color_mapping)
# adata.uns["cluster_coarse_colors"] = np.array()

scv.pl.proportions(
    adata,
    groupby=args.cluster,
    fontsize=plt.rcParams["font.size"],
    figsize=(9,5),
    show=False,
)
plt.savefig(Path(f"{args.outpath}/proportions.pdf"))
plt.close()

print("Computing first- and second-order moments...")

try:
    adata.X = adata.layers["raw"]
except:
    pass

scv.pp.moments(
    adata,
    n_pcs=args.dim_pca,
    n_neighbors=args.k_neighbors,
    copy=False
)

print("Computing velocity...")

scv.tl.velocity(
    adata,
    mode=args.mode,
    copy=False
)
scv.tl.velocity_graph(
    adata,
    copy=False,
)

print("Plotting trajectories...")


import matplotlib as mpl

scv.pl.velocity_embedding_stream(
    adata,
    basis="umap",
    title="",
    linewidth=1,
    size=5,
    color_map=color_map,
#    color=list(color_map.values()),
    show=True, alpha=0.5,
    legend_fontweight="bold",
    fontsize=50,
#    groups="clusters"
    figsize=(7,5),
)


plt.savefig(Path(f"{args.outpath}/trajectories.pdf"))
plt.close()
