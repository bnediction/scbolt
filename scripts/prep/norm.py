#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

import anndata as ad
import numpy as np
import bonesistools as bt
from scipy import sparse


def normalize_by_library_size(adata, layer, target_sum=1e4):
    matrix = adata.layers[layer]

    if sparse.issparse(matrix):
        matrix = matrix.tocsr(copy=True)
        if not np.issubdtype(matrix.dtype, np.floating):
            matrix = matrix.astype(np.float32)
        counts = np.asarray(matrix.sum(axis=1)).ravel()
        counts = counts / target_sum
        counts = counts + (counts == 0)
        matrix.data = np.true_divide(
            matrix.data,
            np.repeat(counts, np.diff(matrix.indptr)),
        )
        adata.layers[layer] = matrix
        return

    matrix = np.asarray(matrix)
    if not np.issubdtype(matrix.dtype, np.floating):
        matrix = matrix.astype(np.float32)
    counts = np.asarray(matrix.sum(axis=1)).ravel()
    counts = counts / target_sum
    counts = counts + (counts == 0)
    np.true_divide(matrix, counts[:, None], out=matrix)
    adata.layers[layer] = matrix


script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="norm",
    description=(
        "Normalize counts with different operations: standardization w.r.t. "
        "library size, log-transformation, scaling and correction of unwanted effects."
    ),
    usage=f"python {script_name} <FILE> <FILE> [<args>]",
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
    help="output file storing normalized counts (format: h5ad)",
)

parser.add_argument(
    "--expression",
    dest="expression",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help=("Expression layer to use.\n" "Default: adata.X."),
)

parser.add_argument(
    "--correction",
    dest="correction",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="unwanted effects to correct (default: None)",
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

if args.expression:
    adata.X = adata.layers[args.expression].copy()

std.print_task("normalizing read counts")

std.print_info("standardizing counts by library size (layer=norm)")
adata.layers["norm"] = adata.X.copy()
normalize_by_library_size(adata, layer="norm", target_sum=1e4)

std.print_info("performing log-transformation (layer=log-norm)")
bt.sct.pp.log1p(
    adata,
    expression="norm",
    key_added="log-norm",
    max_memory=args.max_memory,
    copy=False,
)

std.print_info("scaling to unit variance and zero mean (layer=scale)")
bt.sct.pp.scale(
    adata,
    expression="log-norm",
    key_added="scale",
    copy=False,
)

if args.correction:
    std.print_info("correcting unwanted effects (layer: correct)")
    adata.layers["correct"] = adata.layers["log-norm"].copy()
    bt.sct.tl.regress_out(
        adata,
        keys=args.correction,
        layer="correct",
        intercept=False,
        copy=False,
        n_jobs=args.jobs,
    )
    bt.sct.pp.scale(adata, expression="correct", copy=False)
else:
    std.print_info("no unwanted effects specified")
    adata.layers["correct"] = adata.layers["scale"].copy()

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
std.write_h5ad(adata, filename=args.outfile, compression="gzip")
