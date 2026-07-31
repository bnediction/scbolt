#!/usr/bin/env python

import argparse
import os
from pathlib import Path

import anndata as ad
import bonesistools as bt
import numpy as np
from scipy import sparse

from scbolt import cli, console, omics


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

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="norm",
        description=(
            "Normalize counts with different operations: normalization w.r.t. "
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
        required=True,
        metavar="LITERAL",
        help="Expression layer containing raw counts. Required.",
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

    console.print_task(f"loading AnnData (file={console.format_path(args.infile)})")

    adata = ad.read_h5ad(args.infile)

    console.print_task("normalizing read counts")

    console.print_info("normalizing counts by library size (layer=norm)")
    adata.layers["norm"] = adata.layers[args.expression].copy()
    normalize_by_library_size(adata, layer="norm", target_sum=1e4)

    console.print_info("performing log-transformation (layer=log-norm)")
    bt.omics.pp.log1p(
        adata,
        expression="norm",
        key_added="log-norm",
        max_memory=args.max_memory,
        copy=False,
    )

    if args.correction:
        console.print_info("correcting unwanted effects (layer: correct)")
        adata.layers["correct"] = adata.layers["log-norm"].copy()
        bt.omics.tl.regress_out(
            adata,
            keys=args.correction,
            layer="correct",
            intercept=False,
            copy=False,
            n_jobs=args.jobs,
        )
        bt.omics.pp.scale(adata, expression="correct", copy=False)
    else:
        console.print_info("no unwanted effects specified")
        bt.omics.pp.scale(
            adata,
            expression="log-norm",
            key_added="correct",
            copy=False,
        )

    console.print_task(f"saving AnnData (file={console.format_path(args.outfile)})")
    omics.drop_expression_matrices(adata, layers=("norm", "scale"))
    omics.write_h5ad(adata, filename=args.outfile, compression="gzip")


if __name__ == "__main__":
    main()
