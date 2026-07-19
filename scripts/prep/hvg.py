#!/usr/bin/env python

import argparse
import os
from pathlib import Path

import anndata as ad
import bonesistools as bt

from scbolt import cli, console

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="hvg",
    description="Estimate top highly variable genes.",
    usage=f"python {script_name} <FILE> <FILE> [<args>]",
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)",
)

parser.add_argument(
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing top highly variable genes (format: txt)",
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of highly variable genes to select (default: None)",
)

parser.add_argument(
    "--method",
    dest="method",
    type=str,
    required=False,
    default="loess",
    choices=["loess", "binning"],
    metavar="[loess | binning]",
    help="method used for identifying highly variable genes (default: loess)",
)

parser.add_argument(
    "--expression",
    dest="expression",
    type=str,
    required=True,
    metavar="LITERAL",
    help=(
        "Expression layer used for HVG selection. Expected data: counts with "
        "loess, otherwise log-normalized counts. Required."
    ),
)

parser.add_argument(
    "--span",
    dest="span",
    action=cli.Range,
    type=float,
    min=0,
    max=1,
    required=False,
    default=0.3,
    help=(
        "fraction of cells used when estimating the variance in the loess model (used "
        "only if method='loess', default: 0.3)"
    ),
)

parser.add_argument(
    "--bins",
    dest="bins",
    type=int,
    required=False,
    default=20,
    metavar="INT",
    help="number of bins for binning the mean gene expression (default: 20)",
)

parser.add_argument(
    "--batch",
    dest="batch",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="column name in adata.obs distinguishing batches (default: None)",
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

adata = ad.read_h5ad(f"{args.infile}")

if args.hvg is not None:
    if args.hvg > len(adata.var):
        raise ValueError(
            f"invalid value for parameter 'hvg': number of hvg ({args.hvg}) is greater than number of genes in adata ({adata.n_vars})"
        )

if "highly_variable" in adata.var:
    del adata.var["highly_variable"]
if "highly_variable_rank" in adata.var:
    del adata.var["highly_variable_rank"]
if "means" in adata.var:
    del adata.var["means"]
if "variances" in adata.var:
    del adata.var["variances"]
if "variances_norm" in adata.var:
    del adata.var["variances_norm"]
console.print_task(
    "estimating highly variable genes "
    f"({console.format_hvg_parameters(method=args.method, number=args.hvg)})"
)
bt.omics.pp.hvg(
    adata,
    expression=args.expression,
    method=args.method,
    span=args.span,
    n_bins=args.bins,
    n_features=args.hvg,
    batch_key=args.batch,
    batch_selection="rank",
)
adata._inplace_subset_var(adata.var.highly_variable)

console.print_result(f"identified {adata.n_vars} highly variable genes")

with open(args.outfile, "w") as file:
    for gene in adata.var.index:
        file.write(f"{gene}\n")
