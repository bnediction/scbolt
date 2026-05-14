#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse, cli
from pathlib import Path

import math
import numpy as np

import pandas as pd
import anndata as ad
import bonesistools as bt

parser = argparse.ArgumentParser(
    prog="bin_smirnov",
    description="""
    Binarize clusters using Kolmogorov-Smirnov test.
    """,
    usage="python bin_ks.py [-h] <FILE> <FILE> --cluster <LITERAL> [<args>]",
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing predicted binarized values (format: csv)",
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in 'adata.obs' distinguishing cell populations (required)",
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used (if not specified, use adata.X; expected logarithmized data)",
)

parser.add_argument(
    "--is-log",
    dest="is_log",
    action="store_true",
    required=False,
    help="specify whether data matrix is logarithmized",
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
    help="minimum log2 fold-change in absolute value for a gene to be binarized (default: 0.25)",
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
    help="significance level or probability of rejecting null hypothesis that gene is not differentially expressed (default: 0.05)",
)

parser.add_argument(
    "--correction",
    dest="correction",
    type=str,
    required=False,
    default="benjamini-hochberg",
    choices=["benjamini-hochberg", "bonferroni"],
    metavar="[benjamini-hochberg|bonferroni]",
    help="method used for correcting the significance level (default: benjamini-hochberg)",
)

parser.add_argument(
    "--use-rep",
    dest="use_rep",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="embedding projection in adata.obsm used for plotting percentage of cluster-related binarization (default: None)",
)

parser.add_argument(
    "--filter-genes",
    dest="filter_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="input file storing interest genes to pass filtering (if not specified, all genes are considered)",
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading file {str(args.infile)}")

adata = ad.read_h5ad(args.infile)

if args.layer:
    adata.X = adata.layers[args.layer].copy()

if args.filter_genes:
    std.print_info(
        f"filtering genes by considering only those specified in {args.filter_genes}"
    )
    with open(args.filter_genes) as file:
        adata = adata[:, [line.strip() for line in file.readlines()]]

ks_df = bt.sct.tl.smirnov_tests(
    adata,
    groupby=args.cluster,
    groups="all",
    reference="rest",
    alternative="two-sided",
    corr_method=args.correction,
    pval_cutoff=args.alpha,
    layer=args.layer,
    copy=True,
)

logfoldchanges_df = bt.sct.tl.calculate_logfoldchanges(
    adata,
    groupby=args.cluster,
    layer=args.layer,
    is_log=args.is_log,
    cluster_rebalancing=False,
    filter_logfoldchanges=lambda x: abs(x) > args.logfc,
)

ks_df = pd.merge(
    ks_df,
    logfoldchanges_df,
    left_on=["names", "group"],
    right_on=["names", "group"],
    how="inner",
)
ks_df = ks_df.query(
    "(signs == -1 & logfoldchanges > 0) | (signs == 1 & logfoldchanges < 0)"
)

cluster_bin = pd.DataFrame(
    data=np.nan, index=adata.obs[args.cluster].cat.categories, columns=adata.var.index
)

for row in ks_df.itertuples():
    cluster_bin.at[row.group, row.names] = 1 if row.logfoldchanges > 0 else 0

if args.use_rep:
    embedding_label = (
        args.use_rep[2:].lower()
        if args.use_rep.startswith("X_")
        else args.use_rep.lower()
    )
    std.print_task(
        f"plotting {embedding_label.lower()} with respect to cluster-related binarization percentage"
    )
    pct_bin = (cluster_bin.count(axis=1) / cluster_bin.shape[1]).to_dict()
    adata.obs[f"pct_bin_{args.cluster}"] = adata.obs[args.cluster].map(pct_bin)
    bt.sct.pl.embedding_plot(
        adata,
        obs=f"pct_bin_{args.cluster}",
        use_rep=args.use_rep,
        xlabel=r"$\mathrm{{{}_{{1}}}}$".format(embedding_label),
        ylabel=r"$\mathrm{{{}_{{2}}}}$".format(embedding_label),
        zlabel=r"$\mathrm{{{}_{{3}}}}$".format(embedding_label),
        figwidth=6,
        s=4,
        alpha=1,
        add_legend=True,
        lgd_params={
            "title": "pct bin",
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": bt.sct.pl.get_color("black"),
            "shadow": False,
        },
        n_components=3 if adata.obsm[args.use_rep].shape[1] > 2 else 2,
        background_visible=False,
        outfile=Path(f"{os.path.dirname(args.outfile)}/pct_bin_{args.cluster}.pdf"),
    )

std.print_task(
    f"saving Kolmogorov-Smirnov results in {os.path.dirname(args.outfile)}/ks_results.csv"
)
ks_df.to_csv(
    Path(f"{os.path.dirname(args.outfile)}/ks_results.csv"), sep=",", index=True
)

std.print_task(f"saving predicted binarized values in {str(args.outfile)}")
cluster_bin.to_csv(args.outfile, sep=",", index=True)
