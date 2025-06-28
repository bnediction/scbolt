#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse, cli
from pathlib import Path

import anndata as ad
import scanpy as sc

parser = argparse.ArgumentParser(
    prog="hvg",
    description=
    """
    Estimate top highly variable genes.
    """,
    usage="python hvg.py <FILE> <FILE> [<args>]"
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)"
)

parser.add_argument(
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing top highly variable genes (format: txt)"
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    type=int,
    required=False,
    default=None,
    help="number of highly variable genes (default: None)"
)

parser.add_argument(
    "--method",
    dest="method",
    type=str,
    required=False,
    default="seurat_v3",
    choices=["seurat", "cell_ranger", "seurat_v3"],
    metavar="[seurat|cell_ranger|seurat_v3]",
    help="method used for identifying highly variable genes (default: seurat_v3)"
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help=
    """
    layer used (expects counting data when method='seurat_v3', otherwise logarithmized data. \
    if not specified, use layer 'counts' with method='seurat_v3', otherwise layer 'log-norm')
    """
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
    help="fraction of cells used when estimating the variance in the loess model (used only if method='Seurat_v3', default: 0.3)"
)

parser.add_argument(
    "--bins",
    dest="bins",
    type=float,
    required=False,
    default=20,
    help="number of bins for binning the mean gene expression (default: 20)"
)

parser.add_argument(
    "--batch",
    dest="batch",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="column name in adata.obs distinguishing batches (default: None)"
)

args = parser.parse_args()

if args.layer is None:
    args.layer = "counts" if args.method=="seurat_v3" else "log-norm"

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

adata = ad.read_h5ad(f"{args.infile}")

if args.hvg is not None:
    if args.hvg > len(adata.var):
        raise argparse.ArgumentError(f"invalid value for parameter 'hvg': number of hvg ({args.hvg}) is greater than number of genes in adata ({adata.n_vars})")

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
sc.pp.highly_variable_genes(
    adata,
    layer=args.layer,
    flavor=args.method,
    span=args.span,
    n_bins=args.bins,
    n_top_genes=args.hvg,
    batch_key=args.batch,
    inplace=True
)
if args.method == "seurat_v3":
    adata._inplace_subset_var(adata.var.highly_variable_rank < args.hvg)
else:
    adata._inplace_subset_var(adata.var.highly_variable)

std.print_result(f"{adata.n_vars} highly variable genes selected")

with open(args.outfile, "w") as file:
    for gene in adata.var.index:
        file.write(f"{gene}\n")
