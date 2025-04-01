#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import argparse
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
    help="integration-based file (h5ad format)"
)

parser.add_argument(
    "specifics",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="condition-based input file(s) (h5ad format)"
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    default=None,
    help="condition-based output file(s) (h5ad format. If not specified, replace input file(s))"
)

parser.add_argument(
    "--conditions",
    dest="conditions",
    type=str,
    required=True,
    action=bt.argtype.Required_length,
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

bt.utils.std.print_task("data loading")

bt.utils.std.print_info("loading integrated sample")
integrated_adata = ad.read_h5ad(args.integrated)
bt.utils.std.print_info("loading condition-dependant samples")
condition_adatas = [ad.read_h5ad(infile) for infile in args.specifics]

bt.utils.std.print_info("cleaning unecessary data")
for column in args.columns:
    if column in integrated_adata.obs:
        del integrated_adata.obs[column]
    for adata in condition_adatas:
        if column not in adata.obs:
            raise KeyError(f"column `{column}` not found in adata.obs")

bt.utils.std.print_task("information transfer")

bt.adt.pp.transfer_obs_sti(
    adata=integrated_adata,
    adatas=condition_adatas,
    obs=args.columns,
    conditions=args.conditions,
    condition_colname=args.condition_column,
    copy=False
)

bt.utils.std.print_task("data saving")

integrated_adata.write_h5ad(
    filename=args.outfile if args.outfile else args.integrated,
    compression="gzip"
)
