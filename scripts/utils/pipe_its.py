#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import argparse
from pathlib import Path
from bonesistools.utils.std import (
    print_task,
    print_info
)

import anndata as ad

parser = argparse.ArgumentParser(
    prog="integrated-to-specific information transfer",
    description="""send information from integrated data towards multiple datasets, each one containing one condition""",
    usage="""python pipe_its.py [-h] <FILE> <FILE [FILE ...]> --columns <COLUMNS [COLUMNS ...]> [OPTIONS]"""
)

parser.add_argument(
    "integrated",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="integration-based file (h5ad format)"
)

parser.add_argument(
    "infiles",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="condition-based input file(s) (h5ad format)"
)

parser.add_argument(
    "--outfiles",
    dest="outfiles",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    default=None,
    nargs="+",
    help="condition-based output file(s) (h5ad format. If not specified, replace input file(s))"
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

print_task("data loading")

print_info("loading integrated sample")
integrated_adata = ad.read_h5ad(args.integrated)
print_info("loading condition-dependant samples")
condition_adatas = [ad.read_h5ad(infile) for infile in args.infiles]

print_task("information transfer")

for column in args.columns:
    for adata in condition_adatas:
        if column in adata.obs:
            del adata.obs[column]
    if column not in integrated_adata.obs:
        raise KeyError(f"column `{column}` not found in integrated_adata.obs")

for adata in condition_adatas:
    cond = integrated_adata.obs[args.condition] == adata.uns[args.condition]
    df = integrated_adata.obs.loc[cond][args.columns]
    adata.obs = adata.obs.merge(
        right=df,
        how="left",
        left_index=True,
        right_index=True
    )

print_task("data saving")

for adata, outfile in zip(condition_adatas, args.outfiles):
    adata.write_h5ad(filename=outfile, compression="gzip")
