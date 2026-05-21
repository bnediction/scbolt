#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import math
import random
import numpy as np

import anndata as ad
import cellrank as cr
import bonesistools as bt

bt.sct.pl.set_default_params()

parser = argparse.ArgumentParser(
    prog="cellrank",
    description="""
    Estimate macrostates using generalized perron cluster cluster analysis (GPCCA)
    with respect to velocity, potency and similarity-based kernels.
    See Lange et al. (2022) <https://www.nature.com/articles/s41592-021-01346-6>.
    """,
    usage="python cellrank_macrostates.py <FILE> <FILE> [--csv <FILE>] [<args>]",
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts and rna velocities (format: h5ad)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing cellrank macrostates (format: h5ad)",
)

parser.add_argument(
    "--csv",
    dest="csv",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output file storing macrostates (format: csv)",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="column name in adata.obs distinguishing clusters",
)

parser.add_argument(
    "--cytotrace-score",
    dest="cytotrace_score",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="column name in adata.obs storing cytotrace cell potency scores (default: None)",
)

parser.add_argument(
    "--scvelo-first-moment",
    dest="scvelo_first_moment",
    type=str,
    required=False,
    default="Ms",
    metavar="LITERAL",
    help="layer in adata.layers storing first order moments of spliced counts (default: 'Ms')",
)

parser.add_argument(
    "--scvelo-velocity",
    dest="scvelo_velocity",
    type=str,
    required=False,
    default="velocity",
    metavar="LITERAL",
    help="layer in adata.layers storing scvelo velocities (default: 'velocity')",
)

parser.add_argument(
    "--method",
    dest="method",
    type=str,
    required=False,
    default="stability",
    choices=["stability", "top_n", "eigengap", "eigengap_coarse"],
    metavar="[stability|top_n|eigengap|eigengap_coarse]",
    help="method used to select terminal states (default: stability)",
)

parser.add_argument(
    "--states",
    dest="states",
    type=int,
    required=False,
    default=10,
    metavar="INT",
    help="number of states (default: 10)",
)

parser.add_argument(
    "--initial-states",
    dest="initial_states",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of initial states (default: 1)",
)

parser.add_argument(
    "--terminal-states",
    dest="terminal_states",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of terminal states (used when --method value is 'top_n', default: None)",
)

parser.add_argument(
    "--stability",
    dest="stability",
    type=float,
    required=False,
    default=0.96,
    metavar="FLOAT",
    help="minimum stability for a state to be selected as a final macrostate (used when --method value is 'stability', default: 0.96)",
)

parser.add_argument(
    "--alpha",
    dest="alpha",
    type=float,
    required=False,
    default=1,
    metavar="FLOAT",
    help="weight given to the deviation of an eigenvalue from one (only used when --method value is 'eigengap' or 'eigengap_coarse', default: 1)",
)

parser.add_argument(
    "--size",
    dest="size",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of cells in each macrostate (default: 50)",
)

parser.add_argument(
    "--seed",
    dest="seed",
    type=float,
    required=False,
    default=random.random(),
    metavar="FLOAT",
    help="random number generator (default: random)",
)

parser.add_argument(
    "--jobs",
    dest="jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of allocated processors",
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading data from {str(args.infile)}")
adata = ad.read_h5ad(args.infile)

std.print_task("computing kernels")

std.print_info("computing RNA velocity-based kernel")
velocity_kernel = cr.kernels.VelocityKernel(
    adata, xkey=args.scvelo_first_moment, vkey=args.scvelo_velocity
)
velocity_kernel.compute_transition_matrix(seed=args.seed)

if args.cytotrace_score:
    std.print_info("computing cell development potential-based kernel")
    potency_kernel = cr.kernels.CytoTRACEKernel(adata)
    scores = adata.obs[args.cytotrace_score].copy()
    scores -= scores.min()
    scores /= scores.max()
    potency_kernel._pseudotime = 1 - scores
    potency_kernel.compute_transition_matrix(n_jobs=args.jobs)
else:
    std.print_warning(
        "cell development potential-based kernel is not computed: please specify argument --cytotrace-score"
    )

std.print_info("computing similarity-based kernel")
connectivity_kernel = cr.kernels.ConnectivityKernel(adata)
connectivity_kernel.compute_transition_matrix()

std.print_info("combining kernels")
if args.cytotrace_score:
    combined_kernel = (
        0.4 * velocity_kernel + 0.4 * potency_kernel + 0.2 * connectivity_kernel
    )
else:
    combined_kernel = 0.8 * velocity_kernel + 0.2 * connectivity_kernel

std.print_task(
    "estimating macrostates using generalized perron cluster cluster analysis (GPCCA)"
)
gpcca = cr.estimators.GPCCA(combined_kernel)

with std.disable_print():
    gpcca.fit(cluster_key=args.obs, n_states=args.states, n_cells=args.size)

try:
    gpcca.predict_initial_states(n_states=args.initial_states, n_cells=args.size)
    found_initial_states = True
except ValueError as e:
    if str(e) == "No macrostates have been selected.":
        found_initial_states = False
        std.print_warning("no initial states have been predicted")
    else:
        raise

try:
    gpcca.predict_terminal_states(
        method=args.method,
        n_states=args.terminal_states,
        stability_threshold=args.stability,
        alpha=args.alpha,
        n_cells=args.size,
        allow_overlap=True,
    )
    found_final_states = True
except ValueError as e:
    if str(e) == "No macrostates have been selected.":
        found_final_states = False
        std.print_warning("no final states have been predicted")
    else:
        raise

adata.obs["macrostate"] = adata.obs["macrostates_fwd"]
del adata.obs["macrostates_fwd"]

if found_initial_states is True:
    adata.obs["init_states"] = adata.obs["init_states_fwd"]
    del adata.obs["init_states_fwd"]
else:
    adata.obs["initial_states"] = np.nan
    adata.obs["initial_states"] = adata.obs["initial_states"].astype("category")

if found_final_states is True:
    adata.obs["final_states"] = adata.obs["term_states_fwd"]
    del adata.obs["term_states_fwd"]
else:
    adata.obs["final_states"] = np.nan
    adata.obs["final_states"] = adata.obs["final_states"].astype("category")

cellrank_plot_dir = Path(os.path.dirname(args.outfile))
std.print_task(f"plotting CellRank outputs in {os.path.relpath(cellrank_plot_dir)}")
macrostate_files = {
    "macrostate": cellrank_plot_dir / "umap_cellrank.pdf",
    "init_states": cellrank_plot_dir / "umap_init_states.pdf",
    "final_states": cellrank_plot_dir / "umap_final_states.pdf",
}

for obs, file in macrostate_files.items():
    if len(adata.obs[obs].cat.categories) > 0:
        bt.sct.pl.embedding_plot(
            adata,
            obs=obs,
            use_rep="X_umap",
            figheight=6,
            figwidth=8,
            xlabel=r"$\mathrm{UMAP_{1}}$",
            ylabel=r"$\mathrm{UMAP_{2}}$",
            zlabel=r"$\mathrm{UMAP_{3}}$",
            s=4,
            alpha=1,
            add_labels=True,
            add_legend=True,
            lgd_params={
                "title": obs,
                "ncol": math.ceil(
                    len(adata.obs[obs].astype("category").cat.categories) / 16
                ),
                "markerscale": 5,
                "frameon": True,
                "edgecolor": bt.sct.pl.get_color("black"),
                "shadow": False,
            },
            text={"fontsize": 15, "fontweight": "extra bold"},
            n_components=3 if adata.obsm["X_umap"].shape[1] > 2 else 2,
            background_visible=False,
            outfile=file,
        )
    else:
        std.print_warning(f"no plotting for '{obs}': no state found")

std.print_task(f"saving AnnData object in {str(args.outfile)}")
adata.write_h5ad(filename=args.outfile, compression="gzip")

if args.csv:
    std.print_task(f"saving KNNbs macrostates in {str(args.csv)}")
    adata.obs["macrostate"].to_csv(args.csv, sep=",", index=True)
