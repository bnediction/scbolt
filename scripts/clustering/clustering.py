#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import random

import numpy as np
import anndata as ad
import scanpy as sc
import bonesistools as bt

bt.sct.pl.set_default_params()

parser = argparse.ArgumentParser(
    prog="clustering",
    description=
    """
    Compute principal components, compute closest and shared-nearest neighbors,
    cluster cells using leiden algorithm and embed the neighborhood graph in
    umap or t-sne projection, useful for visualizing high-dimensional data
    in a reduced space.
    """,
    usage="python clustering.py <FILE> <FILE> [<args>]"
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)"
)

parser.add_argument(
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing neighbors and embedding projection (format: h5ad)"
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used (if not specified, use adata.X)"
)

parser.add_argument(
    "--adjacency",
    dest="adjacency",
    type=str,
    required=False,
    default="knn",
    choices=["knn","snn"],
    metavar="[knn|snn]",
    help="neighbors connectivities used for leiden clustering (default: knn)"
)

parser.add_argument(
    "--embedding",
    dest="embedding",
    type=str,
    required=False,
    default="umap",
    choices=["umap","tsne"],
    metavar="[umap|tsne]",
    help="embedding projection (default: umap)"
)

parser.add_argument(
    "--pca-dimension",
    dest="pca_dimension",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of computed principal components (default: 50)"
)

parser.add_argument(
    "--clustering-dimension",
    dest="clustering_dimension",
    type=int,
    required=False,
    default=15,
    metavar="INT",
    help="number of principal components taken into account for clustering cells (default: 15)"
)

parser.add_argument(
    "--embedding-dimension",
    dest="embedding_dimension",
    type=int,
    required=False,
    default=2,
    metavar="INT",
    help="number of embedding dimensions (default: 2)"
)

parser.add_argument(
    "--zero-center",
    dest="zero_center",
    required=False,
    action="store_true",
    help="if true, compute PCA from covariance matrix, otherwise omit zero-centering variables"
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    required=False,
    action="store_true",
    help="use only highly variable genes for PCA projection"
)

parser.add_argument(
    "--neighbors",
    dest="neighbors",
    type=int,
    required=False,
    default=20,
    metavar="INT",
    help="number of closest neighbors (default: 20)"
)

parser.add_argument(
    "--metric",
    dest="metric",
    type=str,
    required=False,
    default="euclidean",
    metavar="METRIC",
    help="metric used for computing closest neighbors and optionally t-sne projection (default: euclidean)"
)

parser.add_argument(
    "--resolution",
    dest="resolution",
    type=float,
    required=False,
    default=0.6,
    metavar="FLOAT",
    help="coarseness of the clustering (default: 0.6)"
)

parser.add_argument(
    "--min-dist",
    dest="min_dist",
    type=float,
    required=False,
    default=0.5,
    metavar="FLOAT",
    help="effective minimum distance between embedded points in umap (default: 0.5)"
)

parser.add_argument(
    "--spread",
    dest="spread",
    type=float,
    required=False,
    default=1.0,
    metavar="FLOAT",
    help="effective scale of embedded points in umap (default: 1.0)"
)

parser.add_argument(
    "--seed",
    dest="seed",
    type=int,
    required=False,
    default=random.random(),
    metavar="FLOAT",
    help="random number generator (default: random)"
)

args = parser.parse_args()

if args.pca_dimension < args.clustering_dimension:
    raise argparse.ArgumentError(
        f"invalid values for arguments: 'pca-dimension' > 'clustering-dimension' not satisfied (pca-dimension: {args.pca_dimension}, clustering-dimension: {args.clustering_dimension})"
    )

label = "UMAP" if args.embedding == "umap" else "t-SNE"

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading file {str(args.infile)}")

adata = ad.read_h5ad(args.infile)

if args.layer:
    adata.X = adata.layers[args.layer].copy()

std.print_task(f"computing top {args.pca_dimension} principal components")
if args.hvg:
    std.print_info(f"use only highly variable genes")
sc.tl.pca(
    adata,
    n_comps=args.pca_dimension,
    zero_center=args.zero_center,
    use_highly_variable=args.hvg,
    random_state=np.random.RandomState(args.seed),
    copy=False
)

std.print_task(f"computing closest neighbors-related connectivities and similarities using top {args.clustering_dimension} principal components")
sc.pp.neighbors(
    adata,
    n_neighbors=args.neighbors,
    use_rep="X_pca",
    n_pcs=args.clustering_dimension,
    metric=args.metric,
    copy=False
)

std.print_task("computing shared nearest neighbors-related connectivities and similarities")
bt.sct.tl.shared_neighbors(
    adata,
    snn_key="shared_neighbors",
    prune_snn = 1/15,
    copy=False
)

std.print_task("clustering cells using leiden algorithm")
sc.tl.leiden(
    adata,
    neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
    resolution=args.resolution,
    key_added=f"leiden",
    random_state=args.seed,
    copy=False
)

std.print_task(f"embedding the neighborhood graph in {args.embedding_dimension} dimensions")
if args.embedding == "umap":
    std.print_info("computing Uniform Manifold Approximation and Projection (UMAP)")
    sc.tl.umap(
        adata,
        neighbors_key="neighbors",
        n_components=args.embedding_dimension,
        min_dist=args.min_dist,
        spread=args.spread,
        random_state=np.random.RandomState(args.seed),
        copy=False
    )
    del adata.uns["umap"]["params"]["random_state"]
elif args.embedding == "tsne":
    std.print_info("computing t-distributed Stochastic Neighborhood Embedding (t-SNE)")
    sc.tl.tsne(
        adata,
        n_pcs=args.embedding_dimension,
        use_rep="X_pca",
        metric=args.metric,
        random_state=np.random.RandomState(args.seed),
        copy=False
    )

std.print_info(f"plotting {label.lower()} with respect to leiden-based clusters")
bt.sct.pl.embedding_plot(
    adata,
    obs="leiden",
    obsm="X_umap" if args.embedding == "umap" else "X_tsne",
    xlabel=r"$\mathrm{{{}_{{1}}}}$".format(label),
    ylabel=r"$\mathrm{{{}_{{2}}}}$".format(label),
    zlabel=r"$\mathrm{{{}_{{3}}}}$".format(label),
    figwidth=6,
    s=2,
    alpha=1,
    add_legend=True,
    lgd_params={
        "title":"clusters",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":bt.sct.pl.get_color("black"),
        "shadow":False
    },
    n_components = 3 if args.embedding_dimension > 2 else 2,
    background_visible=False,
    outfile=Path(f"{os.path.dirname(args.outfile)}/{args.embedding}_leiden.pdf")
)

std.print_task(f"saving data in {str(args.outfile)}")
adata.write_h5ad(
    filename=args.outfile,
    compression="gzip"
)
