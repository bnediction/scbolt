#!/usr/bin/env python

import warnings

import os, argparse
from pathlib import Path

import scanpy as sc
import bonesistools as bt
import scvelo as scv

import numpy as np

import matplotlib.pyplot as plt

bt.adt.pl.set_default_params()

parser = argparse.ArgumentParser(
    prog="velocity",
    description="""Perform scvelo analysis.""",
    usage="python scvelo_velocity.py <FILE> <PATH> [<args>]"
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
    "--cluster",
    dest="cluster",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name such as adata.obs[`LITERAL`] distinguishes clusters"
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

args = parser.parse_args()

if not args.outpath.exists():
    os.makedirs(args.outpath)

warnings.filterwarnings("ignore", category=DeprecationWarning)

bt.utils.std.print_task("data loading")

adata = sc.read_h5ad(args.infile)
n_components = adata.obsm["X_umap"].shape[1]

adata.obs["clusters"] = adata.obs[args.cluster]

adata.uns["colors"] = np.array([bt.adt.pl.COLORS[idx] for idx, _ in enumerate (adata.obs["clusters"].cat.categories)])
color_map = {cluster: bt.adt.pl.COLORS[idx] for idx, cluster in enumerate(adata.obs["clusters"].cat.categories)}

scv.pl.proportions(
    adata,
    groupby=args.cluster,
    fontsize=plt.rcParams["font.size"],
    figsize=(11,5),
    show=False
)
plt.savefig(Path(f"{args.outpath}/proportions.pdf"))
plt.close()

bt.utils.std.print_task("first- and second-order moments computation")

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

with bt.utils.std.disable_print():
    scv.pp.moments(
        adata,
        n_pcs=None,
        n_neighbors=None,
        copy=False
    )

bt.utils.std.print_task("velocity estimation")

with bt.utils.std.disable_print():
    scv.tl.velocity(
        adata,
        mode=args.mode,
        copy=False
    )

bt.utils.std.print_task("velocity graph computation")

with bt.utils.std.disable_print():
    scv.tl.velocity_graph(
        adata,
        copy=False
    )

bt.utils.std.print_task("velocity pseudotime estimation")

with bt.utils.std.disable_print():
    scv.tl.velocity_pseudotime(adata)

bt.utils.std.print_task("PAGA estimation")

with bt.utils.std.disable_print():
    scv.tl.paga(adata, groups=args.cluster)
    adata.uns["transitions_confidence"] = adata.uns["paga"]["transitions_confidence"]

bt.utils.std.print_task("trajectory plotting")

figwidth, figheight = 7, 4
with bt.utils.std.disable_print():
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
    try:
        plt.savefig(Path(f"{args.outpath}/trajectories.pdf"))
    except:
        if os.path.isfile(Path(f"{args.outpath}/trajectories.pdf")):
            os.remove(Path(f"{args.outpath}/trajectories.pdf"))
        plt.savefig(Path(f"{args.outpath}/trajectories.png"))
    plt.close()

fig, _ = bt.adt.pl.embedding_plot(
    adata,
    obs="velocity_pseudotime",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=args.legend,
    figwidth=6,
    s=4,
    alpha=1,
    lgd_params={
        "title":"latent time",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":bt.adt.pl.get_color("black"),
        "shadow":False
    },
    n_components = 3 if adata.obsm["velocity_umap"].shape[1] > 2 and args.plot_3d is True else 2,
    background_visible=False,
    colorbar_scale=0.3,
    colors="gnuplot"
)
with bt.utils.std.disable_print():
    plt.axis("off")
    fig.set_figwidth(fig.get_figwidth()*1.25)
    plt.savefig(Path(f"{args.outpath}/velocity_pseudotime.pdf"))
    plt.close()

fig, ax = bt.adt.pl.embedding_plot(
    adata,
    obs="clusters",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=args.legend,
    figwidth=6,
    s=4,
    alpha=1,
    lgd_params={
        "title":"phenotype",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":bt.adt.pl.get_color("black"),
        "shadow":False
    },
    color=adata.uns["colors"],
    n_components = 3 if adata.obsm["velocity_umap"].shape[1] > 2 and args.plot_3d is True else 2,
    background_visible=False,
)
with bt.utils.std.disable_print():
    plt.axis("off")
    ax = bt.adt.pl.draw_paga(
        adata=adata,
        obs=args.cluster,
        obsm="X_umap",
        edges="transitions_confidence",
        threshold=0.01,
        ax=ax,
        with_labels=False,
        width=2,
        node_size=100,
        node_color=color_map
    )
    plt.savefig(Path(f"{args.outpath}/paga.pdf"))
    plt.close()

bt.utils.std.print_task("data saving")

adata.write_h5ad(filename=f"{args.outpath}/scvelo.h5ad")
