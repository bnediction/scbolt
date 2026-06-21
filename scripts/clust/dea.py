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
from pandas import ExcelWriter

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="dea",
    description="Search for overexpressed genes (markers) between clusters.",
    usage=f"python {script_name} [-h] <FILE> <FILE> [--xlsx <FILE>] --cluster <LITERAL> [<args>]",
    formatter_class=cli.HelpFormatter,
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
    "--method",
    dest="method",
    type=str,
    required=False,
    default="wilcoxon",
    choices=["wilcoxon", "welch", "welch_overestimate"],
    metavar="[wilcoxon | welch | welch_overestimate]",
    help="statistical test used before log2 fold-change estimation (default: wilcoxon)",
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

parser.add_argument(
    "--max-memory",
    dest="max_memory",
    type=cli.Memory,
    required=False,
    default=None,
    metavar="MEMORY",
    help=(
        "maximum memory allocated to chunked BoNesisTools operations "
        "(integers are interpreted as GB)"
    ),
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")

adata = ad.read_h5ad(args.infile)

std.print_task(f"ranking genes (scope=groups, method={args.method})")

markers_df = bt.sct.tl.dea(
    adata,
    groupby=args.cluster,
    method=args.method,
    expression=args.expression,
    is_log=args.is_log,
    correction=args.correction,
    alpha=args.alpha,
    filter_logfoldchanges=lambda x: x > args.logfc,
    max_memory=args.max_memory,
)
markers_df = markers_df.rename(columns={"feature": "gene"})
markers_df = markers_df[
    ["group", "gene", "statistics", "pvals", "pvals_adj", "logfoldchanges"]
]
markers_df = markers_df.sort_values(
    by=["group", "statistics"],
    ascending=[True, False],
    kind="mergesort",
).reset_index(drop=True)

std.print_task(f"saving CSV table (file={std.format_path(args.outfile)})")
markers_df.to_csv(
    args.outfile,
    sep=",",
    index=False,
)

if args.xlsx:
    std.print_task(
        f"saving differential expression workbook (file={std.format_path(args.xlsx)})"
    )
    with ExcelWriter(args.xlsx) as xlsx_writer:
        pd.DataFrame(adata.var_names).to_excel(
            xlsx_writer,
            sheet_name="background",
            header=False,
            index=False,
        )
        for cluster in markers_df["group"].unique():
            markers_df[markers_df["group"] == cluster]["gene"].to_excel(
                xlsx_writer,
                sheet_name=cluster,
                header=False,
                index=False,
            )
