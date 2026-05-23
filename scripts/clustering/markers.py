#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse, cli
from pathlib import Path

import math

import pandas as pd
import anndata as ad
import scanpy as sc
import bonesistools as bt
from pandas import ExcelWriter

parser = argparse.ArgumentParser(
    prog="markers",
    description="Search for overexpressed genes (markers) between clusters.",
    usage="python markers.py [-h] <FILE> <FILE> [--xlsx <FILE>] --cluster <LITERAL> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
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
    help="output file storing marker-metric associations (format: csv)",
)

parser.add_argument(
    "--xlsx",
    dest="xlsx",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="output file storing overexpressed genes, each worksheet corresponding to a cluster (format: xlsx)",
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
    help="layer used (if not specified, use adata.X; expected log-normalized data)",
)

parser.add_argument(
    "--is-log",
    dest="is_log",
    action="store_true",
    required=False,
    help="specify whether the data matrix is log-normalized",
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
    help="minimum log2 fold-change for a gene to be considered as differentially expressed (default: 0.25)",
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
    help="maximum adjusted p-value for a marker gene (default: 0.05)",
)

parser.add_argument(
    "--correction",
    dest="correction",
    type=str,
    required=False,
    default="benjamini-hochberg",
    choices=["benjamini-hochberg", "bonferroni"],
    metavar="[benjamini-hochberg | bonferroni]",
    help="method used for correcting the significance level (default: benjamini-hochberg)",
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading data from {str(args.infile)}")

adata = ad.read_h5ad(args.infile)

if args.layer:
    adata.X = adata.layers[args.layer].copy()

std.print_task("ranking genes for characterizing groups")

sc.tl.rank_genes_groups(
    adata=adata,
    groupby=args.cluster,
    use_raw=False,
    layer=args.layer,
    reference="rest",
    method="wilcoxon",
    tie_correct=True,
    corr_method=args.correction,
)

markers_df = sc.get.rank_genes_groups_df(adata, group=None, pval_cutoff=args.alpha)

std.print_warning(
    "found inconsistencies between log2 fold-changes derived from seurat::FindAllMarkers and scanpy.rank_gene_groups (see <https://www.biostars.org/p/453129/>)"
)
std.print_debug("updating log2 fold-changes")
logfoldchanges_df = bt.sct.tl.calculate_logfoldchanges(
    adata,
    groupby=args.cluster,
    layer=args.layer,
    column_name="logfoldchanges",
    is_log=args.is_log,
    cluster_rebalancing=False,
    filter_logfoldchanges=lambda x: x > args.logfc,
)

markers_df = markers_df.loc[:, markers_df.columns != "logfoldchanges"]

markers_df = pd.merge(
    markers_df,
    logfoldchanges_df,
    left_on=["names", "group"],
    right_on=["names", "group"],
    how="inner",
)

std.print_task(f"saving data in {str(args.outfile)}")
markers_df.to_csv(args.outfile, sep=",", index=False)

if args.xlsx:
    std.print_task(f"saving differentially expressed genes in {str(args.xlsx)}")
    with ExcelWriter(args.xlsx) as xlsx_writer:
        pd.DataFrame(adata.var_names).to_excel(
            xlsx_writer, sheet_name="background", header=False, index=False
        )
        for cluster in markers_df["group"].unique():
            markers_df[markers_df["group"] == cluster]["names"].to_excel(
                xlsx_writer, sheet_name=cluster, header=False, index=False
            )
