#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path

import pickle
import scanpy as sc
from bonesistools import anndatatools as adt

import matplotlib.pyplot as plt
from bonesistools.anndatatools.plotting import (
    fig,
    color
)

parser = argparse.ArgumentParser(
    prog="Single-cell embedding projection",
    description="""Compute embedding space for visualizing high-dimensional data.
    The available dimension reduction algorithm are t-SNE and UMAP.""",
    usage="python embedding.py <FILE> <PATH> [<args>]"
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="counting file (h5ad format)"
)

parser.add_argument(
    "outpath",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "-l", "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used (if not specified, use adata.X)"
)

parser.add_argument(
    "-k", "--k-neighbors",
    dest="k_neighbors",
    type=int,
    required=False,
    default=20,
    metavar="INT",
    help="number of closest neighbors computed when computing KNN graph (default: 20)"
)

parser.add_argument(
    "-ng", "--neighborhood-graph",
    dest="neighborhood_graph",
    type=str,
    required=False,
    default="knn",
    choices=["knn","snn"],
    metavar="[knn | snn]",
    help="neighborhood graph used by Leiden clustering algorithm (default: knn)"
)

parser.add_argument(
    "-z", "--zero-center",
    dest="zero_center",
    required=False,
    action="store_true",
    help="compute standard PCA from covariance matrix if `True`, otherwise omit zero-centering variables"
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    required=False,
    action="store_true",
    help="select the most variable genes for PCA projection"
)

parser.add_argument(
    "-m", "--metric",
    dest="metric",
    type=str,
    required=False,
    default="euclidean",
    metavar="METRIC",
    help="metric used for knn and bbknn-based integration algorithms (default: euclidean)"
)

parser.add_argument(
    "-p", "--dim-pca",
    dest="pca_dimension",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of principal components (default: 50)"
)

parser.add_argument(
    "-c", "--dim-clustering",
    dest="clustering_dimension",
    type=int,
    required=False,
    default=15,
    metavar="INT",
    help="number of principal components taken into account for clustering cells (default: 15)"
)

parser.add_argument(
    "-u", "--dim-umap",
    dest="umap_dimension",
    type=int,
    required=False,
    default=2,
    metavar="INT",
    help="number of embedding dimensions (default: 2)"
)

parser.add_argument(
    "--add-legend",
    dest="legend",
    required=False,
    action="store_true",
    help="add legend to figures"
)

parser.add_argument(
    "--plot-3d",
    dest="plot_3d",
    required=False,
    action="store_true",
    help="plot figures in three dimensions"
)

parser.add_argument(
    "-s", "--seed",
    dest="seed",
    type=int,
    required=False,
    default=None,
    metavar="FLOAT",
    help="random number generator"
)

args = parser.parse_args()

if not args.outpath.exists():
    os.makedirs(args.outpath)

adata = sc.read_h5ad(args.infile)

if args.pca_dimension < max(args.clustering_dimension, args.umap_dimension) or args.clustering_dimension < args.umap_dimension:
    raise argparse.ArgumentError(
        f"invalid values for arguments: dim-pca > dim-clustering > dim-umap not satisfied"
    )

if args.layer:
    adata.X = adata.layers[args.layer]

sc.tl.pca(
    adata,
    zero_center=args.zero_center,
    n_comps=args.pca_dimension,
    use_highly_variable=args.hvg,
    copy=False
)

sc.pp.neighbors(
    adata,
    n_neighbors=args.k_neighbors,
    use_rep="X_pca",
    n_pcs=args.clustering_dimension,
    metric=args.metric,
    key_added="knn",
    copy=False
)
adt.tl.shared_neighbors(
    adata,
    knn_key="knn",
    snn_key="snn",
    prune_snn = 1/15,
    copy=False
)

sc.tl.umap(
    adata,
    neighbors_key=args.neighborhood_graph,
    n_components=args.umap_dimension,
    random_state=args.seed if args.seed else 100
)

fig, _ = adt.pl.embedding_plot(
    adata,
    obs="cluster",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=args.legend,
    figwidth=6,
    s=3,
    alpha=1,
    lgd_params={
        "title":"clusters",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":color.black,
        "shadow":False
    },
    n_components = 3 if args.umap_dimension > 2 and args.plot_3d is True else 2,
    background_visible=False,
    add_labels=True
)
plt.savefig(Path(f"{args.outpath}/umap_clusters.pdf"))
if args.umap_dimension > 2 and args.plot_3d:
    pickle.dump(fig, open(Path(f"{args.outpath}/umap_clusters.fig.pickle"), "wb"))

adata.write_h5ad(filename=f"{args.outpath}/counts.h5ad", compression="gzip")