#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, inspect, std
import argparse, cli
import pkg_resources
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

bt.sct.pl.set_default_params()

parser = argparse.ArgumentParser(
    prog="cytotrace",
    description="""
    Scoring cell potencies.
    """,
    usage="python cytotrace.py <FILE> <FILE> [<args>]"
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts and annotated clustering (format: h5ad)"
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing cell potency predictions (format: h5ad)"
)

parser.add_argument(
    "--csv",
    dest="csv",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output file storing cell potency predictions (format: csv)"
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used corresponding to raw counts or CPM/TPM (if not specified, use adata.X)"
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in adata.obs distinguishing clusters"
)

parser.add_argument(
    "--only-hvg",
    dest="only_hvg",
    action="store_true",
    required=False,
    help="use only highly variable genes for estimating cell potencies"
)

parser.add_argument(
    "--batch-size",
    dest="batch_size",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of cells to process at once for the pipeline steps (recommended: 20000, default: all cells)"
)

parser.add_argument(
    "--smooth-batch-size",
    dest="smooth_batch_size",
    type=int,
    required=False,
    default=1000,
    metavar="INT",
    help="number of cells to subsample for the smoothing by diffusion step (recommended: 1000)"
)

parser.add_argument(
    "--organism",
    dest="organism",
    action=cli.Store_organism,
    default="mouse",
    required=False
)

parser.add_argument(
    "--embedding",
    dest="embedding",
    type=str,
    required=False,
    default="umap",
    choices=["umap","tsne"],
    metavar="[umap|tsne]",
    help="embedding projection used (default: umap)"
)

parser.add_argument(
    "--seed",
    dest="seed",
    type=int,
    required=False,
    default=random.randint(0,1e9),
    metavar="INT",
    help="random number generator (default: random)"
)

parser.add_argument(
    "--jobs",
    dest="jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of allocated processors"
)

s = """data/rna/ctrl/clustering/clusters/annotation.h5ad data/rna/ctrl/trajectories/cytotrace/cytotrace.h5ad --layer counts --cluster leiden --batch-size 20000 --smooth-batch-size 1000 --organism mouse --seed 2 --jobs 16"""

args = parser.parse_args(s.split())

outpath = os.path.dirname(args.outfile)
if not Path(outpath).exists():
    os.makedirs(outpath)

np.random.seed(args.seed)

std.print_task(f"loading file {str(args.infile)}")
adata = ad.read_h5ad(args.infile)

df = bt.sct.tl.anndata_to_dataframe(
    adata,
    obs=args.cluster,
    layer=args.layer
)

counts, clusters = df.iloc[:,:-1], df.iloc[:,-1]

if counts.max().max() <= 20:
    warnings.warn("Input expression data seem to be log2-transformed. Please provide data as raw counts or CPM/TPM.", stacklevel=1)

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
    smooth_chunk_number = math.ceil(args.batch_size/args.smooth_batch_size)
    cores_to_use_for_batch, cores_to_use_for_smooth_batch = cytotrace.calculate_cores_to_use(
        chunk_number=chunk_number,
        smooth_chunk_number=smooth_chunk_number,
        max_cores=args.jobs,
        disable_parallelization=False
    )
    torch.set_num_threads(cores_to_use_for_batch)

std.print_info(f"batch: [chunk: {chunk_number}, cpu cores: {cores_to_use_for_batch}]")
std.print_info(f"smoothing batch: [chunk: {smooth_chunk_number}, cpu cores: {cores_to_use_for_smooth_batch}]")

from cytotrace2_py.cytotrace2_py import run_cytotrace2

run_cytotrace2()

std.print_task("preprocessing data")
if clusters:
    adata_plot = cytotrace.common.gen_utils.process_with_scanpy(counts, clusters.to_frame())
else:
    adata_plot = cytotrace.common.gen_utils.process_with_scanpy(counts)

use_model_dir = pkg_resources.resource_filename(
    package_or_requirement="cytotrace2_py",
    resource_name="resources/models/"
)

model = torch.load(Path(f"{os.path.dirname(inspect.getfile(cytotrace))}/resources/background.pt")).to_dense().t()

original_names = counts.index
subsamples_indices = np.arange(len(counts))
if chunk_number > 1:
    np.random.shuffle(subsamples_indices)
subsamples = np.array_split(subsamples_indices, chunk_number)

predictions = list()
results = list()

std.print_task(f"predicting cell potencies")

for idx in range(chunk_number):
    std.print_info(f"batch {idx+1}")
    chunked_counts = counts.iloc[subsamples[idx], :]
    smooth_by_knn_df = cytotrace.process_subset(
        idx=idx,
        chunked_expression=chunked_counts,
        B_in=model,
        smooth_batch_size=args.smooth_batch_size,
        smooth_cores_to_use=cores_to_use_for_smooth_batch,
        species=args.organism,
        use_model_dir=Path(f"{os.path.dirname(inspect.getfile(cytotrace))}/resources/models/"),
        output_dir=os.path.dirname(args.outfile),
        seed=args.seed,
        disable_verbose=True
    )
    predictions.append(smooth_by_knn_df)

std.print_task(f"aggregating batches")
predicted_df = pd.concat(predictions, ignore_index=False)
predicted_df = predicted_df.loc[original_names]
ranges = np.linspace(0, 1, 7)  
labels = [
    "Differentiated",
    "Unipotent",
    "Oligopotent",
    "Multipotent",
    "Pluripotent",
    "Totipotent"
]

predicted_df.columns = predicted_df.columns.map(lambda x: re.sub(r'cytotrace2_', "", x, flags=re.IGNORECASE).lower())

predicted_df["potency"] = pd.cut(
    predicted_df["score"],
    bins=ranges,
    labels=labels,
    include_lowest=True
)

scores = predicted_df["score"].values
predicted_df["normalized_score"] = (scores-min(scores))/(max(scores)-min(scores))

#embedding_label = "UMAP" if args.embedding == "umap" else "t-SNE"
#use_rep="X_umap" if args.embedding == "umap" else "X_tsne"
#std.print_task(f"plotting {embedding_label.lower()}")
#bt.sct.pl.embedding_plot(
#    adata,
#    obs=f"score",
#    use_rep=args.embedding,
#    xlabel=r"$\mathrm{{{}_{{1}}}}$".format(embedding_label),
#    ylabel=r"$\mathrm{{{}_{{2}}}}$".format(embedding_label),
#    zlabel=r"$\mathrm{{{}_{{3}}}}$".format(embedding_label),
#    figwidth=6,
#    s=4,
#    alpha=1,
#    add_legend=True,
#    lgd_params={
#        "title":"pct bin",
#        "ncol":1,
#        "markerscale":5,
#        "frameon":True,
#        "edgecolor":bt.sct.pl.get_color("black"),
#        "shadow":False
#    },
#    n_components = 3 if adata.obsm[use_rep].shape[1] > 2 else 2,
#    background_visible=False,
#    outfile=Path(f"{os.path.dirname(args.outfile)}/pct_bin_{args.cluster}.pdf")
#)

if args.csv:
    std.print_task(f"saving predicted cell potencies in {str(args.outfile)}")
    predicted_df.to_csv(
        args.csv,
        sep=",",
        index=True
    )
