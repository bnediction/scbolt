#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse, cli
from pathlib import Path

import anndata as ad

parser = argparse.ArgumentParser(
    prog="single-cell cluster labeling",
    description="""Rename labels using user-defined names.""",
    usage="""python cluster_annotation.py [-h] <FILE> <FILE> -c <LITERAL> -n <LITERAL=LITERAL [LITERAL=LITERAL ...]>"""
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="counting file (h5ad format)"
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output file with labels (h5ad format)"
)

parser.add_argument(
    "-c", "--column",
    dest="column",
    type=str,
    required=True,
    metavar="LITERAL",
    help="name of the column in adata.obs from which user want to redefine category names"
)

parser.add_argument(
    "-n", "--name",
    dest="labels",
    action=cli.Store_dict,
    required=True,
    nargs="+",
    help="mapping between old and new names for labels"
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task("data loading")

adata = ad.read_h5ad(args.infile)

std.print_task("cluster labeling")

if args.column not in adata.obs:
    raise KeyError(f"adata.obsm[`{args.column}`] does not exist.")
elif not hasattr(adata.obs[args.column], "cat"):
    raise ValueError("values in adata.obs[`{args.column}`] are not derived from a Categorical type.")
else:
    adata.obs[args.column].replace(args.labels, inplace=True)

std.print_task("data saving")

adata.write_h5ad(filename=args.outfile, compression="gzip")
