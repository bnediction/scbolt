#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import os, argparse
from pathlib import Path
from utils.stdout import disable_print

import pandas as pd
import anndatatools as adt, scanpy as sc, scvelo as scv

import numpy as np

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
    "--metric",
    dest="metric",
    type=str,
    required=False,
    default="euclidean",
    metavar="METRIC",
    help="metric used for knn and bbknn-based integration algorithms (default: euclidean)"
)

parser.add_argument(
    "-c", "--dim-clustering",
    dest="dim_clustering",
    type=int,
    required=False,
    default=15,
    metavar="INT",
    help="number of principal components taken into account for clustering cells (default: 15)"
)

parser.add_argument(
    "--mode",
    dest="mode",
    type=str,
    required=False,
    choices=["deterministic", "stochastic", "dynamical"],
    default="stochastic",
    metavar="[deterministic | stochastic | dynamical]",
    help="mode used to estimate the steady-state model (default: stochastic)"
)

s = """data/rna/ctrl/cluster/tables/counts_labels.h5ad data/rna/ctrl/scvelo --cluster leiden --k-neighbors 30 --dim-clustering 30 --mode stochastic"""
s = """data/rna/treated/cluster/tables/counts_labels.h5ad data/rna/treated/scvelo --cluster leiden --k-neighbors 30 --dim-clustering 30 --mode stochastic"""

args = parser.parse_args(s.split())

if not args.outpath.exists():
    os.makedirs(args.outpath)

print(f"Loading data...")

adata = sc.read_h5ad(args.infile)
n_components = adata.obsm["X_umap"].shape[1]
# adata2 = scv.datasets.pancreas()

adata.obs["clusters"] = adata.obs[args.cluster]

adata.uns["colors"] = np.array([adt.pl.rgb2hex(adt.pl.COLORS[idx]) for idx, _ in enumerate (adata.obs["clusters"].cat.categories)])
color_map = {cluster: adt.pl.rgb2hex(adt.pl.COLORS[idx]) for idx, cluster in enumerate(adata.obs["clusters"].cat.categories)}

scv.pl.proportions(
    adata,
    groupby=args.cluster,
    fontsize=plt.rcParams["font.size"],
    figsize=(11,5),
    show=False
)
plt.savefig(Path(f"{args.outpath}/proportions.pdf"))
plt.close()

print("Computing first- and second-order moments...")

try:
    adata.X = adata.layers["raw"]
except:
    pass

sc.pp.neighbors(
    adata,
    n_neighbors=args.k_neighbors,
    use_rep="X_pca",
    n_pcs=args.dim_clustering,
    metric=args.metric,
    copy=False
)

with disable_print():
    scv.pp.moments(
        adata,
        copy=False
    )

print("Computing velocity...")

with disable_print():
    scv.tl.velocity(
        adata,
        mode=args.mode,
        copy=False
    )

print("Computing velocity graph...")

with disable_print():
    scv.tl.velocity_graph(
        adata,
        copy=False,
        show_progress_bar=False
    )

print("Plotting trajectories...")

figwidth, figheight = 7, 4
with disable_print():
    ax = scv.pl.velocity_embedding_stream(
        adata,
        basis="umap",
        title="",
        linewidth=1,
        size=5,
        color_map=color_map,
        alpha=0.5,
        legend_loc="best",
        legend_fontweight="bold",
        figsize=(figwidth,figheight),
        show=False
    )
    for txt in ax.texts:
        txt.set_visible(False)
plt.savefig(Path(f"{args.outpath}/trajectories.pdf"))
plt.close()

scv.tl.velocity_pseudotime(adata)
scv.pl.scatter(adata, color='velocity_pseudotime', cmap='gnuplot')

