#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import argparse
from pathlib import Path

import anndata as ad

parser = argparse.ArgumentParser(
    prog="data merging",
    description="""Send information from integrated data towards multiple datasets, each one containing one condition.""",
    usage="""python pipe.py [-h] <FILE> <FILE [FILE ...]> --columns <COLUMNS [COLUMNS ...]> [OPTIONS]"""
)

parser.add_argument(
    "integrated",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="integration-based file in h5ad format"
)

parser.add_argument(
    "infiles",
    type=lambda x: Path(x).resolve(),
    metavar="FILE [FILE ...]",
    nargs="+",
    help="condition-based input file(s) in h5ad format"
)

parser.add_argument(
    "--outfiles",
    dest="outfiles",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE [FILE ...]",
    default=None,
    nargs="+",
    help="condition-based output file(s) in h5ad format (not specified: replace input file(s))"
)

parser.add_argument(
    "--columns",
    dest="columns",
    required=True,
    nargs="+",
    help="name of the columns in integrated adata.obs that the user wants to send to control and treated adata"
)

parser.add_argument(
    "--condition",
    dest="condition",
    type=str,
    required=False,
    metavar="LITERAL",
    default="condition",
    help="name of the column in integrated adata.obs matching with control and treated adata.uns[condition] (default: condition)"
)

args = parser.parse_args()

print(f"Loading data...")

condition_adata = [ad.read_h5ad(infile) for infile in args.infiles]
integrated_adata = ad.read_h5ad(args.integrated)

print(f"Merging data...")

for column in args.columns:
    for adata in condition_adata:
        if column in adata.obs:
            del adata.obs[column]
    if column not in integrated_adata.obs:
        raise KeyError(f"{column} does not exist in integrated_adata.obs")

for adata in condition_adata:
    cond = integrated_adata.obs[args.condition] == adata.uns[args.condition]
    df = integrated_adata.obs.loc[cond][args.columns]
    adata.obs = adata.obs.merge(how='left',right=df, left_index=True, right_index=True)

print("Saving data...")

for adata, outfile in zip(condition_adata, args.outfiles):
    adata.write_h5ad(filename=outfile, compression="gzip")
