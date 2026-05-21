#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse, cli
from pathlib import Path

import anndata as ad

parser = argparse.ArgumentParser(
    prog="annotation",
    description="""
    Rename labels using user-defined names. \
    Specified value for parameter '--name' must be a sequence where each element has the following syntax: <old_name>:<new_name>
    """,
    usage="python annotation.py [-h] <FILE> <FILE> --obs <LITERAL> --labels <LITERAL:LITERAL [LITERAL:LITERAL ...]>",
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
    metavar="PATH",
    help="input file storing counts with new labels (format: h5ad)",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in adata.obs where category names are redefined",
)

parser.add_argument(
    "--new-obs",
    dest="new_obs",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="if specified, create a new column in adata.obs corresponding to labels",
)

parser.add_argument(
    "--labels",
    dest="labels",
    action=cli.Store_dict,
    nargs="+",
    required=True,
    help="mapping between old and new names",
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

dict_to_str = ""
add = ""
for k, v in args.labels.items():
    dict_to_str += f"{add}{k}->{v}"
    add = ", "

std.print_task(f"loading data from {str(args.infile)}")

adata = ad.read_h5ad(args.infile)

if args.obs not in adata.obs:
    raise KeyError(f"column '{args.obs}' not found in adata.obs")
elif not hasattr(adata.obs[args.obs], "cat"):
    raise ValueError(
        f"series 'adata.obs[{args.obs}]' does not refer to a categorical variable"
    )

std.print_task(f"renaming labels for column '{args.obs}' ({dict_to_str})")

if args.new_obs is None:
    adata.obs[args.obs].replace(args.labels, inplace=True)
else:
    adata.obs[args.new_obs] = adata.obs[args.obs].replace(args.labels, inplace=False)

std.print_task(f"saving data in {str(args.outfile)}")
adata.write_h5ad(filename=args.outfile, compression="gzip")
