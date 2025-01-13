#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path
from utils.stdout import Section

import scanpy as sc
import cellrank as cr
import anndatatools as adt

import matplotlib.pyplot as plt
from anndatatools.plotting import color

parser = argparse.ArgumentParser(
    prog="Cellrank macrostates computation",
    description="""Perform cellrank analysis to find macrostates.""",
    usage="python cellrank_macrostates.py <FILE> <PATH> [<args>]"
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
    "--macrostate-size",
    dest="macrostate_size",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of cells in each macrostate (default: 50)"
)

parser.add_argument(
    "--initial-states",
    dest="initial_states",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of initial states (default: 1)"
)

parser.add_argument(
    "--terminal-states",
    dest="terminal_states",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of terminal states, used when method = top_n (default: None)"
)

parser.add_argument(
    "--method",
    dest="method",
    type=str,
    required=False,
    default="stability",
    choices=["stability", "top_n", "eigengap", "eigengap_coarse"],
    metavar="[stability | top_n | eigengap | eigengap_coarse]",
    help="method used to select terminal states (default: stability)"
)

parser.add_argument(
    "--stability_threshold",
    dest="stability_threshold",
    type=float,
    required=False,
    default=0.96,
    metavar="FLOAT",
    help="number of terminal states, used when method = stability (default: 0.96)"
)

parser.add_argument(
    "--alpha",
    dest="alpha",
    type=float,
    required=False,
    default=1,
    metavar="FLOAT",
    help="weight given to the deviation of an eigenvalue from one, used when method = eigengap or eigengap_coarse (default: 1)"
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

section = Section(verbose = True)

print(f"Loading data...")

adata = sc.read_h5ad(args.infile)

print(f"Computing kernel...")

section("Computing velocity kernel", reset=True)

vk = cr.kernels.VelocityKernel(adata)
vk.compute_transition_matrix()

section("Computing connectivity kernel")

ck = cr.kernels.ConnectivityKernel(adata)
ck.compute_transition_matrix()

section("Merging kernel")

combined_kernel = 0.8 * vk + 0.2 * ck

print(f"Identifying initial and terminal states...")

g = cr.estimators.GPCCA(combined_kernel)
g.fit(
    cluster_key="clusters",
    n_cells = args.macrostate_size,
    n_states=[4, 20]
)
adata.obs["macrostates"] = adata.obs["macrostates_fwd"]

g.predict_initial_states(
    n_states = args.initial_states,
    n_cells = args.macrostate_size
)

g.predict_terminal_states(
    method=args.method,
    n_states=args.terminal_states,
    n_cells=args.macrostate_size,
    stability_threshold=args.stability_threshold,
    alpha=args.alpha,
    allow_overlap=True
)

fig, _ = adt.pl.embedding_plot(
    adata,
    obs="macrostates_fwd",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=True,
    figwidth=6,
    s=4,
    alpha=1,
    lgd_params={
        "title":"macrostates",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":color.black,
        "shadow":False
    },
    n_components = 3 if adata.obsm["X_umap"].shape[1] > 2 and args.plot_3d is True else 2,
    background_visible=False
)
plt.savefig(Path(f"{args.outpath}/macrostates.pdf"))

fig, _ = adt.pl.embedding_plot(
    adata,
    obs="init_states_fwd",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=True,
    figwidth=6,
    s=4,
    alpha=1,
    lgd_params={
        "title":"macrostates",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":color.black,
        "shadow":False
    },
    n_components = 3 if adata.obsm["X_umap"].shape[1] > 2 and args.plot_3d is True else 2,
    background_visible=False
)
plt.savefig(Path(f"{args.outpath}/initial_states.pdf"))

fig, _ = adt.pl.embedding_plot(
    adata,
    obs="term_states_fwd",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=True,
    figwidth=6,
    s=4,
    alpha=1,
    lgd_params={
        "title":"macrostates",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":color.black,
        "shadow":False
    },
    n_components = 3 if adata.obsm["X_umap"].shape[1] > 2 and args.plot_3d is True else 2,
    background_visible=False
)
plt.savefig(Path(f"{args.outpath}/terminal_states.pdf"))

print("Saving data...")

adata.write_h5ad(filename=f"{args.outpath}/adata.h5ad")