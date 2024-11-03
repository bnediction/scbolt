#!/usr/bin/env python

import warnings

import os, argparse
from pathlib import Path
from utils.stdout import Section, disable_print

import scanpy as sc
import scvelo as scv
import cellrank as cr
import anndatatools as adt

import matplotlib.pyplot as plt
from anndatatools.plotting import (
    fig,
    color
)

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

args = parser.parse_args()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

scv.settings.set_figure_params("scvelo")

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
g.fit(cluster_key="clusters", n_states=[4, 20])
g.predict_initial_states()
g.predict_terminal_states()

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
plt.savefig(Path(f"{fig_outpath}/macrostates.pdf"))

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
plt.savefig(Path(f"{fig_outpath}/initial_states.pdf"))

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
plt.savefig(Path(f"{fig_outpath}/terminal_states.pdf"))

print("Saving data...")

adata.write_h5ad(filename=f"{data_outpath}/cellrank.h5ad")