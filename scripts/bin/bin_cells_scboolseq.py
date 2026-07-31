#!/usr/bin/env python

import argparse
import os
from pathlib import Path

import anndata as ad
import bonesistools as bt
import numpy as np
import pandas as pd
from scboolseq import scBoolSeq

from scbolt import cli, console, omics

script_name = Path(__file__).name

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bin_cells_scboolseq",
        description=(
            "Compute statistical estimators, classify the distribution law for each gene "
            "and binarize cell counts using the scBoolSeq framework.\n"
            "Counts must already be log-normalized (logarithm transformation on CPM, "
            "RPM, TPM or RPKM).\n"
            "See Magaña López et al. (2023) <https://hal.science/hal-04294917/>."
        ),
        usage=f"python {script_name} [-h] <FILE> --outfile <FILE> [--bin <FILE>] [--statistics <FILE>] [<args>]",
        formatter_class=cli.HelpFormatter,
    )

    parser.add_argument(
        dest="infile",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help="input file storing counts (format: h5ad)",
    )

    parser.add_argument(
        "--outfile",
        dest="outfile",
        type=lambda x: Path(x).resolve(),
        required=True,
        metavar="FILE",
        help="output file storing layer 'bin' (format: h5ad)",
    )

    parser.add_argument(
        "--bin",
        dest="bin",
        type=lambda x: Path(x).resolve(),
        required=False,
        default=None,
        metavar="FILE",
        help="output file storing binarization matrix (format: csv)",
    )

    parser.add_argument(
        "--statistics",
        dest="statistics",
        type=lambda x: Path(x).resolve(),
        required=False,
        default=None,
        metavar="FILE",
        help="output file storing computed statistics (format: csv)",
    )

    parser.add_argument(
        "--representation",
        dest="representation",
        type=str,
        required=False,
        default=None,
        metavar="LITERAL",
        help=(
            "Embedding representation in adata.obsm used for plotting binarization "
            "percentages.\n"
            "Default: None."
        ),
    )

    parser.add_argument(
        "--expression",
        dest="expression",
        type=str,
        required=True,
        metavar="LITERAL",
        help=(
            "Expression layer to use. Expected data: log-normalized counts. "
            "Required."
        ),
    )

    parser.add_argument(
        "--quantile",
        dest="quantile",
        action=cli.Range,
        type=float,
        min=0,
        max=1,
        required=False,
        default=0.10,
        help=(
            "quantile used to classify cells as inactive/active when learned distribution "
            "is unimodal (default: 0.10)"
        ),
    )

    parser.add_argument(
        "--zeroes-are-zeroes",
        dest="zeroes_are_zeroes",
        required=False,
        action="store_true",
        help=(
            "binarize zero values to zero instead of NaN when learned distribution is "
            "zero-inflated"
        ),
    )

    parser.add_argument(
        "--filter-genes",
        dest="filter_genes",
        type=lambda x: Path(x).resolve(),
        required=False,
        metavar="FILE",
        help=(
            "input file storing interest genes to pass filtering (if not specified, all "
            "genes are considered)"
        ),
    )

    parser.add_argument(
        "--seed",
        dest="seed",
        type=int,
        required=False,
        default=None,
        metavar="INTEGER",
        help="Random seed used by scBoolSeq internal estimators.",
    )

    args = parser.parse_args()

    if not Path(os.path.dirname(args.outfile)).exists():
        os.makedirs(Path(os.path.dirname(args.outfile)))

    if args.seed is not None:
        np.random.seed(args.seed)

    console.print_task(f"loading AnnData (file={console.format_path(args.infile)})")
    adata = ad.read_h5ad(args.infile)

    console.print_info(f"converting layer '{args.expression}' into dataframe")
    counts_df = bt.omics.tl.to_dataframe(adata, layer=args.expression)

    if args.filter_genes:
        console.print_info(f"filtering genes (file={console.format_path(args.filter_genes)})")
        with open(args.filter_genes) as file:
            counts_df = counts_df[[line.strip() for line in file.readlines()]]

    console.print_task("binarizing cells (method=scBoolSeq)")

    scbool = scBoolSeq(
        margin_quantile=args.quantile,
        zeroinf_binarizer="quantile",
        zeroes_are=0 if args.zeroes_are_zeroes else np.nan,
    )

    console.print_info("estimating parametric distributions")
    with console.suppress_output():
        scbool.fit(counts_df, simulation=False)

    console.print_info("converting counting values into Boolean values")
    with console.suppress_output():
        cell_df = scbool.binarize(counts_df)
        criteria_df = scbool.criteria_.copy()
    missing_genes = [gene for gene in adata.var.index if gene not in cell_df.columns]
    cell_df = cell_df.reindex(columns=adata.var.index)
    criteria_df = criteria_df.reindex(index=adata.var.index)
    criteria_df.loc[missing_genes, "Category"] = "Discarded"
    if not list(cell_df.index) == list(adata.obs.index):
        raise pd.errors.IndexingError(
            "Index values in 'cell_df' not sorted with observations in 'adata'"
        )
    elif not list(cell_df.columns) == list(adata.var.index):
        raise pd.errors.IndexingError(
            "Column values in 'cell_df' not sorted with variables in 'adata'"
        )
    elif not list(criteria_df.index) == list(adata.var.index):
        raise pd.errors.IndexingError(
            "Column values in 'criteria_df' not sorted with variables in 'adata'"
        )
    adata.layers["bin"] = cell_df
    adata.obs["pct_bin"] = (~cell_df.isna()).mean(axis=1)
    adata.var["distribution"] = criteria_df["Category"]

    if args.representation:
        pct_bin_plot = Path(f"{os.path.dirname(args.outfile)}/pct_bin.pdf")
        console.print_task(
            "plotting binarization summaries "
            f"(directory={os.path.relpath(os.path.dirname(args.outfile))})"
        )
        omics.plot_continuous_embedding(
            adata,
            obs="pct_bin",
            embedding=args.representation,
            label=console.format_embedding(args.representation),
            colorbar_label=r"$\% \mathrm{bin}$",
            s=3,
            outfile=pct_bin_plot,
        )

    console.print_task(f"saving AnnData (file={console.format_path(args.outfile)})")
    omics.drop_expression_matrices(
        adata,
        layers=tuple(layer for layer in adata.layers if layer != "bin"),
    )
    omics.write_h5ad(adata, filename=args.outfile, compression="gzip")

    if args.bin:
        console.print_task(f"saving binarized matrix (file={console.format_path(args.bin)})")
        cell_df.to_csv(args.bin, sep=",", index=True)

    if args.statistics:
        console.print_task(
            f"saving statistical estimators (file={console.format_path(args.statistics)})"
        )
        criteria_df.to_csv(args.statistics, sep=",", index=True)


if __name__ == "__main__":
    main()
