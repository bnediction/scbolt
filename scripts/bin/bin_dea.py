#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

import math

import pandas as pd
import anndata as ad
import bonesistools as bt

script_name = Path(__file__).name


parser = argparse.ArgumentParser(
    prog="bin_dea",
    description=(
        "Binarize clusters using differential expression analysis.\n"
        "Supported tests: Wilcoxon rank-sum and Welch tests."
    ),
    usage=f"python {script_name} [-h] <FILE> <FILE> --cluster <LITERAL> [<args>]",
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="Input AnnData file storing expression counts. Expected format: h5ad.",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="Output CSV file storing predicted binarized values.",
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=True,
    metavar="LITERAL",
    help="Observation column distinguishing cell populations. Required.",
)

parser.add_argument(
    "--expression",
    dest="expression",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help=(
        "Expression layer to use. Expected data: log-normalized counts.\n"
        "Default: adata.X."
    ),
)

parser.add_argument(
    "--is-log",
    dest="is_log",
    action="store_true",
    required=False,
    help="Treat the selected expression matrix as log-normalized.",
)

parser.add_argument(
    "--method",
    dest="method",
    type=str,
    required=False,
    default="wilcoxon",
    choices=["wilcoxon", "welch", "welch_overestimate"],
    metavar="[wilcoxon | welch | welch_overestimate]",
    help=("Differential expression test to use.\n" "Default: wilcoxon."),
)

parser.add_argument(
    "--logfc",
    dest="logfc",
    action=cli.Range,
    type=float,
    min=0,
    max=math.inf,
    required=False,
    default=0.25,
    help=(
        "Minimum absolute log2 fold-change required for binarization.\n"
        "Default: 0.25."
    ),
)

parser.add_argument(
    "--alpha",
    dest="alpha",
    action=cli.Range,
    type=float,
    min=0,
    max=1,
    required=False,
    default=0.05,
    help=("Maximum adjusted p-value required for binarization.\n" "Default: 0.05."),
)

parser.add_argument(
    "--correction",
    dest="correction",
    type=str,
    required=False,
    default="benjamini-hochberg",
    choices=["benjamini-hochberg", "bonferroni"],
    metavar="[benjamini-hochberg | bonferroni]",
    help=("Multiple-testing correction method.\n" "Default: benjamini-hochberg."),
)

parser.add_argument(
    "--representation",
    dest="representation",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help=(
        "Embedding representation in adata.obsm used for plotting cluster-related "
        "binarization percentages.\n"
        "Default: None."
    ),
)

parser.add_argument(
    "--filter-genes",
    dest="filter_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help=("Input file listing genes of interest to keep.\n" "Default: all genes."),
)

parser.add_argument(
    "--max-memory",
    dest="max_memory",
    type=cli.Memory,
    required=False,
    default=None,
    metavar="MEMORY",
    help=(
        "Maximum memory allocated to chunked BoNesisTools operations. Integers are "
        "interpreted as GB.\n"
        "Default: no limit."
    ),
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")

adata = ad.read_h5ad(args.infile)

features = list(adata.var_names)
var_subset = None

if args.filter_genes:
    std.print_info(f"filtering genes (file={std.format_path(args.filter_genes)})")
    with open(args.filter_genes) as file:
        var_subset = [line.strip() for line in file.readlines()]

std.print_task(f"ranking genes (scope=groups, method={args.method})")

adata.obs[args.cluster] = adata.obs[args.cluster].cat.remove_unused_categories()

binarizer = bt.sct.tl.DEABinarizer(
    method=args.method,
    correction=args.correction,
    alpha=args.alpha,
    min_abs_logfoldchange=args.logfc,
    max_memory=args.max_memory,
)
binarizer.fit(
    adata,
    obs=args.cluster,
    expression=args.expression,
    is_log=args.is_log,
    var_subset=var_subset,
)

std.print_task("binarizing cell populations (source=differential expression analysis)")

cluster_bin = binarizer.binarize()
cluster_bin = cluster_bin.reindex(columns=pd.Index(features))

if args.representation:
    embedding_label = (
        args.representation[2:].lower()
        if args.representation.startswith("X_")
        else args.representation.lower()
    )
    pct_bin_plot = Path(f"{os.path.dirname(args.outfile)}/pct_bin_{args.cluster}.pdf")
    std.print_task(
        "plotting binarization summaries "
        f"(directory={os.path.relpath(os.path.dirname(args.outfile))})"
    )
    pct_bin = (cluster_bin.count(axis=1) / cluster_bin.shape[1]).to_dict()
    adata.obs[f"pct_bin_{args.cluster}"] = (
        adata.obs[args.cluster].map(pct_bin).astype(float)
    )
    bt.sct.pl.embedding(
        adata,
        obs=f"pct_bin_{args.cluster}",
        use_rep=args.representation,
        xlabel=std.axis_label(embedding_label, 1),
        ylabel=std.axis_label(embedding_label, 2),
        zlabel=std.axis_label(embedding_label, 3),
        figwidth=6,
        s=4,
        alpha=1,
        show_legend=True,
        colorbar_scale=0.8,
        n_components=3 if adata.obsm[args.representation].shape[1] > 2 else 2,
        background_visible=False,
        outfile=pct_bin_plot,
    )

dea_results = Path(f"{os.path.dirname(args.outfile)}/dea_results.csv")
std.print_task(f"saving DEA results (file={std.format_path(dea_results)})")
binarizer.dea_.to_csv(dea_results, sep=",", index=False)

std.print_task(f"saving binarized matrix (file={std.format_path(args.outfile)})")
cluster_bin.to_csv(args.outfile, sep=",", index=True)
