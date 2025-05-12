#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import std
import argparse, cli
from pathlib import Path

import anndata as ad
import bonesistools as bt

parser = argparse.ArgumentParser(
    prog="specific-to-integrated information transfer",
    description="""send information from multiple datasets towards integrated dataset""",
    usage="""python pipe_sti.py [-h] <FILE> <FILE [FILE ...]> --outfile <FILE> --conditions <[LITERAL ...]> --columns <COLUMN [COLUMN ...]> [OPTIONS]"""
)

parser.add_argument(
    "integrated",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="integration-based file (format: h5ad)"
)

parser.add_argument(
    "specifics",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="condition-based input file(s) (format: h5ad)"
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    default=None,
    help="condition-based output file(s) (format: h5ad, if not specified, replace input file(s))"
)

parser.add_argument(
    "--conditions",
    dest="conditions",
    type=str,
    required=True,
    action=cli.Required_length,
    min=2,
    metavar="LITERAL",
    help="condition related to each dataset (ordered with h5ad specifics)",
)

parser.add_argument(
    "--columns",
    dest="columns",
    required=True,
    nargs="+",
    metavar="COLUMN",
    help="name of the columns in integrated adata.obs that the user wants to send to control and treated adata"
)

parser.add_argument(
    "--condition-column",
    dest="condition_column",
    type=str,
    required=False,
    metavar="LITERAL",
    default="condition",
    help="name of the column in integrated adata.obs matching with control and treated adata.uns[condition] (default: condition)"
)

args = parser.parse_args()

std.print_task("loading data")

std.print_info(f"loading integrated sample ({str(args.integrated)})")
integrated_adata = ad.read_h5ad(args.integrated)
std.print_info(f"loading specific samples ({', '.join(map(str, args.specifics))})")
condition_adatas = [ad.read_h5ad(infile) for infile in args.specifics]

std.print_info("cleaning unecessary data")
for column in args.columns:
    if column in integrated_adata.obs:
        del integrated_adata.obs[column]
    for adata in condition_adatas:
        if column not in adata.obs:
            raise KeyError(f"column `{column}` not found in adata.obs")

std.print_task("transferring information from specific samples to integrated sample")

bt.sct.pp.transfer_obs_sti(
    adata=integrated_adata,
    adatas=condition_adatas,
    obs=args.columns,
    conditions=args.conditions,
    condition_colname=args.condition_column,
    copy=False
)

std.print_task(f"saving data ({str(args.outfile)})")

integrated_adata.write_h5ad(
    filename=args.outfile if args.outfile else args.integrated,
    compression="gzip"
)
