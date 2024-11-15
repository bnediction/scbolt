#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path

import scanpy as sc
import anndatatools as adt

import matplotlib.pyplot as plt
from anndatatools.plotting import color

parser = argparse.ArgumentParser(
    prog="scvelo of sc-RNAseq data",
    description="""From sc-RNAseq data recorded in the hdf5 format,
    compute cell sub-populations in each clusters.
    Two methods can be used:
    1) "center" method, computing the cells closest to the cluster-related barycenter
    2) "extremity" method, computing the cells furthest from other cluster-related barycenters""",
    usage="python macrostates.py <FILE> <PATH> [-- center <LITERAL...>] [-- extremity <LITERAL...>] [<args>]"
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
    "--obs",
    dest="obs",
    type=str,
    required=False,
    default="cluster",
    metavar="LITERAL",
    help="column name in adata.obs distinguishing clusters (default: cluster)"
)

parser.add_argument(
    "--center",
    dest="center",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="cluster names for which macrostates correspond to the cells closest to the barycenter (default = None)"
)

parser.add_argument(
    "--extremity",
    dest="extremity",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="cluster names for which macrostates correspond to the cells furthest from other clusters (default = None)"
)

parser.add_argument(
    "--obsm",
    dest="obsm",
    type=str,
    required=False,
    default="X_umap",
    metavar="LITERAL",
    help="embedding space used in adata.obsm (default: X_umap)"
)

parser.add_argument(
    "--dimension",
    dest="dimension",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of components taken into account in adata.obsm[`obsm`] (default: maximum)"
)

parser.add_argument(
    "--macrostate-size",
    dest="macrostate_size",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of cells in each macrostate (default: 50)"
)

parser.add_argument(
    "--plot-3d",
    dest="plot_3d",
    required=False,
    action="store_true",
    help="plot figures in three dimensions"
)

args = parser.parse_args()

if not args.outpath.exists():
    os.makedirs(args.outpath)

adt.pl.set_default()

print(f"Loading data...")

adata = sc.read_h5ad(args.infile)

if args.dimension is None:
    args.dimension = adata.obsm[args.obsm].shape[1]

print(f"Computing macrostates...")

adt.tl.subclusters(
    adata,
    obs=args.obs,
    obsm=args.obsm,
    n_components=args.dimension,
    key="macrostates",
    n_neighbors=args.macrostate_size,
    include_center=args.center,
    include_extremity=args.extremity,
    copy=False
)

fig, _ = adt.pl.embedding_plot(
    adata,
    obs="macrostates",
    obsm=args.obsm,
    xlabel=r"$\mathrm{UMAP_{1}}$" if args.obsm == "X_umap" else r"$\mathrm{c_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$" if args.obsm == "X_umap" else r"$\mathrm{c_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$" if args.obsm == "X_umap" else r"$\mathrm{c_{3}}$",
    add_legend=True,
    figwidth=6,
    s=4,
    alpha=1,
    lgd_params={
        "title":"clusters",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":color.black,
        "shadow":False
    },
    n_components = 3 if adata.obsm[args.obsm].shape[1] > 2 and args.plot_3d is True else 2,
    background_visible=False,
)
plt.savefig(Path(f"{args.outpath}/macrostates.pdf"))
plt.close()

print("Saving data...")

adata.write_h5ad(filename=f"{args.outpath}/adata.h5ad")