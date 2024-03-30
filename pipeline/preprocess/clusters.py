#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path
from utils.argtype import Store_prefix

import pickle
import scanpy as sc
import anndatatools as adt

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
from anndatatools.plotting import (
    fig,
    color
)

parser = argparse.ArgumentParser(
    prog="Clusterization of sc-RNAseq data",
    description="""From one-condition sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    perform dimension reduction using PCA, create clusters using leiden algorithm,
    run t-SNE and UMAP algorithm, search for gene markers and compare markers and
    signatures in order to provide useful information about potential cell-types
    of each cluster.""",
    usage="python clusterization.py <FILE> <PATH> [<args>]"
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
    "--prefix",
    dest="prefix",
    action=Store_prefix,
    required=False,
    default="",
    help="prefix for each saving file"
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
    dest="dim_pca",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of principal components (default: 50)"
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
    "-u", "--dim-umap",
    dest="dim_umap",
    type=int,
    required=False,
    default=2,
    metavar="INT",
    help="number of embedding dimensions (default: 2)"
)

parser.add_argument(
    "-r", "--resolution",
    dest="resolution",
    type=float,
    required=False,
    default=0.6,
    metavar="FLOAT",
    help="parameter value controlling the coarseness of the clustering when using Leiden algorithm (default: 0.6)"
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

parser.add_argument(
    "-v", "--verbose",
    dest="verbose",
    required=False,
    default=False,
    action="store_true",
    help="get summarizing information about cluster in stdout"
)

args = parser.parse_args()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

print(f"Loading data...")

adata = sc.read_h5ad(args.infile)

if args.dim_pca < max(args.dim_clustering, args.dim_umap) or args.dim_clustering < args.dim_umap:
    raise argparse.ArgumentError(
        f"dimension incoherence: dim_pca > dim_clustering > dim_umap not satisfied"
    )

default_seed = args.seed if args.seed else 100

color_d = {
    "G1": color.blue,
    "G2M": color.red,
    "S": color.green
}
phase = adata.obs["pypairs_cc_prediction"]

print("Computation of principal components (pca)...")

adata.X = adata.layers["correct"]
sc.tl.pca(
    adata,
    zero_center=args.zero_center,
    n_comps=args.dim_pca,
    use_highly_variable=args.hvg,
    copy=False
)

print(f"Computation of clusters (leiden)")

sc.pp.neighbors(
    adata,
    n_neighbors=args.k_neighbors,
    use_rep="X_pca",
    n_pcs=args.dim_clustering,
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
if args.neighborhood_graph == "knn":
    sc.tl.leiden(
        adata,
        neighbors_key="knn",
        resolution=args.resolution,
        key_added=f"leiden"
    )
elif args.neighborhood_graph == "snn":
    obsp = adata.uns["snn"]["similarities_key"]
    sc.tl.leiden(
        adata,
        resolution=args.resolution,
        adjacency=adata.obsp[obsp].copy(),
        key_added=f"leiden"
    )

print("Computation of embedding components (umap)...")

sc.tl.umap(
    adata,
    neighbors_key="knn",
    n_components=args.dim_umap,
    random_state=default_seed
)

print("Plot of embedding components...")

fig, _ = adt.pl.embedding_plot(
    adata,
    obs="leiden",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=args.legend,
    figwidth=6,
    s=2,
    alpha=1,
    lgd_params={
        "title":"clusters",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":color.black,
        "shadow":False
    },
    n_components = 3 if args.dim_umap > 2 and args.plot_3d is True else 2,
    background_visible=False
)
plt.savefig(Path(f"{fig_outpath}/{args.prefix}umap_leiden"))
if args.dim_umap > 2 and args.plot_3d:
    pickle.dump(fig, open(Path(f"{fig_outpath}/{args.prefix}umap_leiden.fig.pickle"), "wb"))

fig, _ = adt.pl.embedding_plot(
    adata,
    obs="pypairs_cc_prediction",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=args.legend,
    figwidth=6,
    s=2,
    alpha=1,
    colors=[color.blue, color.red, color.green],
    lgd_params={
        "title":"phases",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":color.black,
        "shadow":False
    },
    n_components = 3 if args.dim_umap > 2 and args.plot_3d is True else 2,
    background_visible=False
)
plt.savefig(Path(f"{fig_outpath}/{args.prefix}umap_phases"))
if args.dim_umap > 2 and args.plot_3d:
    pickle.dump(fig, open(Path(f"{fig_outpath}/{args.prefix}umap_phases.fig.pkl"), "wb"))

for metric in ["total_counts", "pct_counts_mitochondrion"]:
    fig, ax = plt.subplots(nrows=1, ncols=1)
    if metric == "total_counts":
        cmap = "Greens"
        label = r"$\# \mathrm{read\ counts}$"
    elif metric == "pct_counts_mitochondrion":
        cmap = "Blues"
        label = r"$\frac{\# \mathrm{mitochondrion\ counts}}{\# \mathrm{read\ counts}}$"
    mapping = ax.scatter(adata.obsm["X_umap"][:,0], adata.obsm["X_umap"][:,1], s=2, c=adata.obs[metric], cmap=cmap, alpha=1)
    cbar = fig.colorbar(mapping)
    cbar.set_label(label, loc="center", labelpad=5)
    ax.set_xlabel(r"$\mathrm{UMAP_{1}}$")
    ax.set_ylabel(r"$\mathrm{UMAP_{2}}$")
    plt.sca(ax)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
    ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
    plt.savefig(f"{fig_outpath}/{args.prefix}umap_{metric}")

print("Saving data...")

adata.write_h5ad(filename=f"{data_outpath}/{args.prefix}counts.h5ad", compression="gzip")