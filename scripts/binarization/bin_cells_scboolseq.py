#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse, cli
from pathlib import Path

import anndata as ad
import bonesistools as bt

import numpy as np
import pandas as pd

from scboolseq import scBoolSeq

parser = argparse.ArgumentParser(
    prog="bin_cells_scboolseq",
    description=
    """
    Compute statistical estimators, classify distribution law for each gene \
    and binarize cell counts using scBoolSeq framework. \
    Counts must be already log-normalized (logarithm transformation on CPM, RPM, TPM or RPKM). \
    See Magaña López et al. (2023) <https://hal.science/hal-04294917/>.
    """,
    usage=""""python bin_cells_scboolseq.py [-h] <FILE ...> --outfile <FILE> [--bin <FILE>] [--statistics FILE] [<args>]"""
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)"
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing layer 'bin' (format: h5ad)"
)

parser.add_argument(
    "--bin",
    dest="bin",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output file storing binarization matrix (format: csv)"
)

parser.add_argument(
    "--statistics",
    dest="statistics",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output file storing computed statistics (format: csv)"
)

parser.add_argument(
    "--labels",
    dest="labels",
    action=cli.Required_length,
    type=str,
    min=2,
    required=False,
    default=None,
    metavar="LITERAL",
    help="labels related to each dataset (ordered with h5ad files, required when multiple infiles)",
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used corresponding to log-normalized counts (if not specified, use adata.X)"
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
    help="quantile classifying cells into inactive/active when learnt distribution is unimodal (default: 0.10)"
)

parser.add_argument(
    "--zeroes-are-zeroes",
    dest="zeroes_are_zeroes",
    required=False,
    action="store_true",
    help="binarize zero-values to zero instead of nan when learnt distribution is zero-inflated"
)

parser.add_argument(
    "--filter-genes",
    dest="filter_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="input file storing interest genes to pass filtering (if not specified, all genes are considered)"
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading file {str(args.infile)}")
adata = ad.read_h5ad(args.infile)

std.print_debug(f"converting layer '{args.layer}' into dataframe")
counts_df = bt.sct.tl.anndata_to_dataframe(
    adata,
    layer=args.layer
)

if args.filter_genes:
    std.print_info(f"filtering genes by considering only those specified in {args.filter_genes}")
    with open(args.filter_genes) as file:
        counts_df = counts_df[[line.strip() for line in file.readlines()]]

std.print_task("binarizing cells")

scbool = scBoolSeq(
    margin_quantile=args.quantile,
    zeroinf_binarizer="zero_or_not",
    zeroes_are=0 if args.zeroes_are_zeroes else np.nan
)

std.print_info("estimating parametric distributions")
with std.disable_print():
    scbool.fit(
        counts_df,
        simulation=False
    )

std.print_info("converting counting values into Boolean values")
with std.disable_print():
    cell_df = scbool.binarize(counts_df)
    criteria_df = scbool.criteria_.copy()
for gene in set(adata.var.index) - set(cell_df):
    cell_df[gene] = np.nan
    criteria_df.loc[gene] = [*[np.nan]*15, "Discarded"]
cell_df = cell_df[adata.var.index]
criteria_df = criteria_df.loc[adata.var.index]
if not list(cell_df.index) == list(adata.obs.index):
    raise pd.errors.IndexingError("Index values in 'cell_df' not sorted with observations in 'adata'")
elif not list(cell_df.columns) == list(adata.var.index):
    raise pd.errors.IndexingError("Column values in 'cell_df' not sorted with variables in 'adata'")
elif not list(criteria_df.index) == list(adata.var.index):
    raise pd.errors.IndexingError("Column values in 'criteria_df' not sorted with variables in 'adata'")
adata.layers["bin"] = cell_df
adata.obs["pct_bin"] = (~cell_df.isna()).mean(axis=1)
adata.var["distribution"] = criteria_df["Category"]

std.print_task(f"saving data in {str(args.outfile)}")
adata.write_h5ad(
    filename=args.outfile,
    compression="gzip"
)

if args.bin:
    std.print_task(f"saving binarized matrix in {str(args.bin)}")
    cell_df.to_csv(
        args.bin,
        sep=",",
        index=True
    )

if args.statistics:
    std.print_task(f"saving statistical estimators in {str(args.statistics)}")
    criteria_df.to_csv(
        args.statistics,
        sep=",",
        index=True
    )
