#!/usr/bin/env python

import os
import inspect
import std
import argparse
import cli
from pathlib import Path

import re

import random
import math
import numpy as np

import pandas as pd
import anndata as ad
import bonesistools as bt

import torch
import cytotrace2_py as cytotrace

import matplotlib.pyplot as plt
import warnings

std.set_default_plot_params(bt.sct.pl)

parser_description = """Compute scores related to cell development potential (lower the score, higher the differentiation potential) and classify cells by their cell potency using the CytoTRACE framework.

There are six cell potency-based classes:
    - totipotency: ability to divide or differentiate into all cell types
    - pluripotency: ability to differentiate into endoderm, ectoderm or mesoderm
    - multipotency: ability to differentiate into cell types unrelated from its common path
    - oligopotency: ability to differentiate into a few cell types
    - unipotency: ability to differentiate into one cell type
    - differentiation: already differentiated into its mature cell type

See Kang et al. (2024) <https://doi.org/10.1101/2024.03.19.585637>.
"""

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="potency",
    description=parser_description,
    usage=f"python {script_name} <FILE> <FILE> [<args>]",
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts and annotated clustering (format: h5ad)",
)

parser.add_argument(
    "outpath",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output directory storing results",
)

parser.add_argument(
    "--h5ad",
    dest="h5ad",
    type=Path,
    required=False,
    default=None,
    metavar="FILENAME",
    help="output file storing cell potency predictions (format: h5ad)",
)

parser.add_argument(
    "--csv",
    dest="csv",
    type=Path,
    required=False,
    default=None,
    metavar="FILENAME",
    help="output file storing cell potency predictions (format: csv)",
)

parser.add_argument(
    "--expression",
    dest="expression",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help=(
        "Expression layer to use. Expected data: raw counts or CPM/TPM.\n"
        "Default: adata.X."
    ),
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in adata.obs distinguishing clusters",
)

parser.add_argument(
    "--batch-size",
    dest="batch_size",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of cells to process at once for the pipeline steps (recommended: 20000, default: all cells)",
)

parser.add_argument(
    "--smooth-batch-size",
    dest="smooth_batch_size",
    type=int,
    required=False,
    default=1000,
    metavar="INT",
    help="number of cells to subsample for the smoothing by diffusion step (recommended/default: 1000)",
)

parser.add_argument(
    "--organism",
    dest="organism",
    action=cli.Store_organism,
    choices=["mouse", "human"],
    default="mouse",
    required=False,
)

parser.add_argument(
    "--representation",
    dest="representation",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help=(
        "Embedding representation in adata.obsm used for plotting.\n" "Default: None."
    ),
)

parser.add_argument(
    "--seed",
    dest="seed",
    type=int,
    required=False,
    default=random.randint(0, 1_000_000_000),
    metavar="INT",
    help="random seed (default: random)",
)

parser.add_argument(
    "--jobs",
    dest="jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of allocated processors (default: 1)",
)

args = parser.parse_args()

if not args.outpath.exists():
    os.makedirs(args.outpath)

np.random.seed(args.seed)

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")
adata = ad.read_h5ad(args.infile)

counts = bt.sct.tl.anndata_to_dataframe(adata, layer=args.expression)

if counts.max().max() <= 20:
    warnings.warn(
        "Input expression data seem to be log2-transformed. Please provide data as raw counts or CPM/TPM.",
        stacklevel=1,
    )

if args.batch_size is None:
    args.batch_size = len(counts)
elif args.batch_size > len(counts):
    args.batch_size = len(counts)

if args.smooth_batch_size is None:
    args.smooth_batch_size = min(len(counts), args.batch_size)
elif args.smooth_batch_size > len(counts) or args.smooth_batch_size > args.batch_size:
    args.smooth_batch_size = min(len(counts), args.batch_size)

with std.disable_print():
    chunk_number = math.ceil(len(counts) / args.batch_size)
    smooth_chunk_number = math.ceil(args.batch_size / args.smooth_batch_size)
    cores_to_use_for_batch, cores_to_use_for_smooth_batch = (
        cytotrace.calculate_cores_to_use(
            chunk_number=chunk_number,
            smooth_chunk_number=smooth_chunk_number,
            max_cores=args.jobs,
            disable_parallelization=False,
        )
    )
    torch.set_num_threads(cores_to_use_for_batch)

std.print_debug(f"batch: [chunk: {chunk_number}, cpu cores: {cores_to_use_for_batch}]")
std.print_debug(
    f"smoothing batch: [chunk: {smooth_chunk_number}, cpu cores: {cores_to_use_for_smooth_batch}]"
)

model = torch.load(
    Path(f"{os.path.dirname(inspect.getfile(cytotrace))}/resources/background.pt")
)
model = model.t()

original_names = counts.index
subsamples_indices = np.arange(len(counts))
if chunk_number > 1:
    np.random.shuffle(subsamples_indices)
subsamples = np.array_split(subsamples_indices, chunk_number)

predictions = list()
results = list()

std.print_task("predicting cell potencies")

with std.disable_print():
    for idx in range(chunk_number):
        chunked_counts = counts.iloc[subsamples[idx], :]
        smooth_by_knn_df = cytotrace.process_subset(
            idx=idx,
            chunked_expression=chunked_counts,
            B_in=model,
            smooth_batch_size=args.smooth_batch_size,
            smooth_cores_to_use=cores_to_use_for_smooth_batch,
            species=args.organism,
            use_model_dir=Path(
                f"{os.path.dirname(inspect.getfile(cytotrace))}/resources/models/"
            ),
            output_dir=args.outpath,
            seed=args.seed,
            disable_verbose=True,
        )
        predictions.append(smooth_by_knn_df)

std.print_task("aggregating batch results")
potency_df = pd.concat(predictions, ignore_index=False)
potency_df = potency_df.loc[original_names]
ranges = np.linspace(0, 1, 7)
labels = [
    "differentiated",
    "unipotent",
    "oligopotent",
    "multipotent",
    "pluripotent",
    "totipotent",
]

potency_df.columns = potency_df.columns.map(
    lambda x: re.sub(r"cytotrace2_", "", x, flags=re.IGNORECASE).lower()
)

potency_df["potency"] = pd.cut(
    potency_df["score"], bins=ranges, labels=labels, include_lowest=True
)

scores = potency_df["score"].copy().values
scores -= scores.min()
scores /= scores.max()
potency_df["normalized_score"] = scores

if args.csv:
    csv_outfile = args.outpath / args.csv
    std.print_task(f"saving cell potency table (file={std.format_path(csv_outfile)})")
    potency_df.to_csv(csv_outfile, sep=",", index=True)

adata.obs = adata.obs.merge(
    right=potency_df.add_prefix("cytotrace_"),
    how="left",
    left_index=True,
    right_index=True,
)

try:
    embedding_label = args.representation.split("_")[1]
except IndexError:
    embedding_label = args.representation
plot_dir = os.path.relpath(args.outpath)
std.print_task(f"plotting potency outputs (directory={plot_dir})")
for obs in ["score", "normalized_score", "potency"]:
    bt.sct.pl.embedding(
        adata,
        obs=f"cytotrace_{obs}",
        representation=args.representation,
        xlabel=std.axis_label(embedding_label, 1),
        ylabel=std.axis_label(embedding_label, 2),
        zlabel=std.axis_label(embedding_label, 3),
        figwidth=6 if obs == "potency" else 8,
        s=8,
        legend={
            "title": obs,
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": bt.sct.pl.get_color("black"),
            "shadow": False,
        },
        n_components=3 if adata.obsm[args.representation].shape[1] > 2 else 2,
        background_visible=False,
        outfile=Path(f"{args.outpath}/cytotrace_{obs}.pdf"),
    )

fig, ax, _ = bt.sct.pl.distribution(
    adata,
    obs="cytotrace_score",
    groupby=args.cluster,
    sort="descending",
    points=True,
)
ylim_min, ylim_max = 0, 1
plt.ylim((ylim_min, ylim_max))
twin_ax = ax.twinx()
twin_ax.set_yticks(
    np.linspace(
        (ylim_max - ylim_min) / (2 * len(labels)),
        1 - ((ylim_max - ylim_min) / (2 * len(labels))),
        len(labels),
    )
)
twin_ax.set_yticklabels(labels)
twin_ax.tick_params(axis="y", labelsize=14, length=0)
fig.tight_layout()
plt.hlines(
    y=ranges,
    xmin=ax.get_xlim()[0],
    xmax=ax.get_xlim()[1],
    colors=bt.sct.pl.get_color("black"),
    linestyles="-",
    linewidth=0.2,
)
plt.savefig(Path(f"{args.outpath}/boxplot_cytotrace_score.pdf"))

bt.sct.pl.distribution(
    adata,
    obs="cytotrace_normalized_score",
    groupby="cluster",
    sort="descending",
    points=True,
    outfile=Path(f"{args.outpath}/boxplot_cytotrace_normalized_score.pdf"),
)

if args.h5ad:
    h5ad_outfile = args.outpath / args.h5ad
    std.print_task(f"saving AnnData (file={std.format_path(h5ad_outfile)})")
    std.write_h5ad(adata, filename=h5ad_outfile, compression="gzip")
