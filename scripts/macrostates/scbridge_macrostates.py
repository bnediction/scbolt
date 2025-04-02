#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import scanpy as sc
import bonesistools as bt

import matplotlib.pyplot as plt

bt.adt.pl.set_default_params()

parser = argparse.ArgumentParser(
    prog="macrostates computation",
    description="""Compute cell sub-populations in each cluster.
    Two methods can be used:
    1) "center" method, computing the cells closest to the cluster-related barycenter
    2) "extremity" method, computing the cells furthest from other cluster-related barycenters""",
    usage="python scbridge_macrostates.py <FILE> <PATH> [-- center <LITERAL...>] [-- extremity <LITERAL...>] [<args>]"
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="preprocessed input file (h5ad format)"
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="preprocessed output file storing 'macrostates' in adata.obs (h5ad format)"
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
    nargs="*",
    default=None,
    metavar="LITERAL",
    help="cluster names for which macrostates correspond to the cells closest to the barycenter (default = None)"
)

parser.add_argument(
    "--extremity",
    dest="extremity",
    type=str,
    required=False,
    nargs="*",
    default=None,
    metavar="LITERAL",
    help="cluster names for which macrostates correspond to the cells furthest from other clusters (default = None)"
)

parser.add_argument(
    "--exclude",
    dest="exclude",
    required=False,
    action="store_true",
    help="exclude clusters not in `--center` and `--extremity` for computing subclusters with `--extremity`"
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

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task("data loading")

adata = sc.read_h5ad(args.infile)

if args.dimension is None:
    args.dimension = adata.obsm[args.obsm].shape[1]

exclude = set(adata.obs[args.obs].cat.categories).difference(set(args.center).union(set(args.extremity))) if args.exclude is True else None

std.print_task("macrostate computation")

bt.adt.tl.subclusters(
    adata,
    obs=args.obs,
    obsm=args.obsm,
    n_components=args.dimension,
    key="macrostates",
    n_neighbors=args.macrostate_size,
    include_center=args.center,
    include_extremity=args.extremity,
    exclude_for_computation=exclude,
    copy=False
)

std.print_task("embedding component plotting")

fig, _ = bt.adt.pl.embedding_plot(
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
        "title":"macrostates",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":bt.adt.pl.get_color("black"),
        "shadow":False
    },
    n_components = 3 if adata.obsm[args.obsm].shape[1] > 2 and args.plot_3d is True else 2,
    background_visible=False,
)
plt.savefig(Path(f"{os.path.dirname(args.outfile)}/macrostates.pdf"))
plt.close()

std.print_task("data saving")

adata.write_h5ad(filename=args.outfile)