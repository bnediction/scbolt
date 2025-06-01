#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import numpy as np

import pandas as pd

def merge(scboolseq_val, dea_val, scboolseq_distribution):
    if scboolseq_distribution == "Discarded":
        return dea_val
    if scboolseq_distribution == "ZeroInf":
        if np.isnan(scboolseq_val) or scboolseq_val==0:
            return dea_val
        elif dea_val==0:
            return np.nan
        else:
            return 1
    elif scboolseq_distribution in ["Unimodal", "Bimodal"]:
        if scboolseq_val==dea_val:
            return scboolseq_val
        elif np.isnan(scboolseq_val):
            return dea_val
        elif np.isnan(dea_val):
            return scboolseq_val
        else:
            return np.nan
    else:
        raise ValueError(f"invalid parameter value for 'category': expected 'Discarded', 'ZeroInf', 'Bimodal' or 'Unimodal' but received '{scboolseq_distribution}'.")

parser = argparse.ArgumentParser(
    prog="bin_merge",
    description=
    """
    Binarize clusters using scboolseq and differential expression analysis results.
    """,
    usage="python bin_merge.py [-h] <FILE> <FILE> --cluster <LITERAL> [<args>]"
)

parser.add_argument(
    "--scboolseq",
    dest="scboolseq",
    type=lambda x: Path(x).resolve(),
    nargs=2,
    required=True,
    metavar="FILE",
    help="input files storing scboolseq results, first one corresponding to binarized clusters and second one to gene-specific distributions (required)"
)

parser.add_argument(
    "--dea",
    dest="dea",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="input file storing dea results (required)"
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing predicted binarized values (format: csv)"
)

parser.add_argument(
    "--pct-bin",
    dest="pct_bin",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output file storing proportion of binarized values (format: csv)"
)


args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading scboolseq and dea results")

scboolseq_bin = pd.read_csv(
    args.scboolseq[0],
    index_col=0,
    sep=","
)

scboolseq_distribution = pd.read_csv(
    args.scboolseq[1],
    index_col=0,
    sep=","
).iloc[:, 0]

dea_bin = pd.read_csv(
    args.dea,
    index_col=0,
    sep=","
)

std.print_task("binarizing clusters using scboolseq and dea binarization results")

if not set(scboolseq_bin.columns) == set(scboolseq_bin.columns):
    raise KeyError(f"column names different in scboolseq and dea dataframes")
if not set(scboolseq_bin.index) == set(scboolseq_bin.index):
    raise KeyError(f"index names different in scboolseq and dea dataframes")

merge_bin = pd.DataFrame(
    data=np.nan,
    index=scboolseq_bin.index,
    columns=scboolseq_bin.columns
)

for idx in merge_bin.index:
    for col in merge_bin.columns:
        merge_bin.at[idx, col] = merge(
            scboolseq_bin.loc[idx,col],
            dea_bin.loc[idx,col],
            scboolseq_distribution=scboolseq_distribution[col]
        )

pct_bin = pd.concat(
    [
        (~scboolseq_bin.isna()).sum(axis=1)/len(scboolseq_bin.columns),
        (~dea_bin.isna()).sum(axis=1)/len(dea_bin.columns),
        (~merge_bin.isna()).sum(axis=1)/len(merge_bin.columns)
    ],
    axis=1,
    keys=["scboolseq", "dea", "merge"]
).round(5)

std.print_result(f"proportion of binarized values:\n{pct_bin}")

std.print_task(f"saving binarized matrix in {str(args.outfile)}")

merge_bin.to_csv(
    args.outfile,
    sep=",",
    index=True
)

if args.pct_bin:
    std.print_task(f"saving proportion of binarized values in {str(args.pct_bin)}")
    pct_bin.to_csv(
        args.pct_bin,
        sep=",",
        index=True
    )
