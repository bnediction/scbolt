#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import argparse
from pathlib import Path

import anndata as ad

parser = argparse.ArgumentParser(
    prog="data merging",
    description="""Send information from integrated data towards control and treated data.""",
    usage="""python right_join.py [-h] <FILE> <FILE> <FILE> --condition <LITERAL [LITERAL ...]> [OPTIONS]"""
)

parser.add_argument(
    "integrated",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="integration-based file in h5ad format"
)

parser.add_argument(
    "control",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="control condition-based file in h5ad format"
)

parser.add_argument(
    "treated",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="treated condition-based file in h5ad format"
)

parser.add_argument(
    "--out-control",
    dest="out_control",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    default=None,
    help="control condition-based output file in h5ad format (not specified: replace infile)"
)

parser.add_argument(
    "--out-treated",
    dest="out_treated",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    default=None,
    help="treated condition-based output file in h5ad format (not specified: replace infile)"
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

ctrl_adata = ad.read_h5ad(args.control)
treated_adata = ad.read_h5ad(args.treated)
integrated_adata = ad.read_h5ad(args.integrated)

print(f"Merging data...")

for column in args.columns:
    if column in ctrl_adata.obs:
        del ctrl_adata.obs[column]
    if column in treated_adata.obs:
        del treated_adata.obs[column]
    if column not in integrated_adata.obs:
        raise KeyError(f"{column} does not exist in integrated_adata.obs")

cond_ctrl = integrated_adata.obs[args.condition] == ctrl_adata.uns[args.condition]
cond_treated = integrated_adata.obs[args.condition] == treated_adata.uns[args.condition]

ctrl_df = integrated_adata.obs.loc[cond_ctrl][args.columns]
treated_df = integrated_adata.obs.loc[cond_treated][args.columns]

ctrl_adata.obs = ctrl_adata.obs.merge(how='left',right=ctrl_df, left_index=True, right_index=True)
treated_adata.obs = treated_adata.obs.merge(how='left',right=treated_df, left_index=True, right_index=True)

print("Saving data...")

if args.out_control is None:
    ctrl_adata.write_h5ad(filename=args.control, compression="gzip")
else:
    ctrl_adata.write_h5ad(filename=args.out_control, compression="gzip")

if args.out_treated is None:
    treated_adata.write_h5ad(filename=args.treated, compression="gzip")
else:
    treated_adata.write_h5ad(filename=args.out_treated, compression="gzip")
