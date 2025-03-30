#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import argparse
from pathlib import Path
from utils.stdout import (
    print_task,
    print_info
)

import anndata as ad
import anndatatools as adt

parser = argparse.ArgumentParser(
    prog="info transfer",
    description="""send information (obs, var, layers) from one dataset (right) towards another dataset (left)""",
    usage="""python transfer_info.py [-h] <FILE> <FILE> --outfile <FILE> --conditions <[LITERAL ...]> --columns <COLUMN [COLUMN ...]> [OPTIONS]"""
)

parser.add_argument(
    "left",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="left-sided file (h5ad format)"
)

parser.add_argument(
    "right",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="right-sided file (h5ad format)"
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    default=None,
    help="output file (h5ad format. If not specified, replace left-sided file)"
)

parser.add_argument(
    "--obs",
    dest="obs",
    required=False,
    nargs="+",
    metavar="LITERAL",
    help="name of the columns in right-sided adata.obs sent to left-sided adata"
)

parser.add_argument(
    "--var",
    dest="var",
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="name of the columns in right-sided adata.var sent to left-sided adata"
)

parser.add_argument(
    "--layers",
    dest="layers",
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="name of the layers in right-sided adata.var sent to left-sided adata"
)

parser.add_argument(
    "--index",
    dest="index",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="name of the columns in [left|right] adata.obs used as index with initial index (useful when identical barcodes in index, default: None)"
)

args = parser.parse_args()

print_task("data loading")

print_info("loading left sample")
left_ad = ad.read_h5ad(args.left)
print_info("loading right sample")
right_ad = ad.read_h5ad(args.right)

if args.index:
    print_task("index setting")
    for adata in [left_ad, right_ad]:
        adt.pp.set_index(
            adata=adata,
            keys=args.index,
            axis=0,
            copy=False
        )

if args.obs:
    print_task("observation transfer")
    right_ad.obs = right_ad.obs.loc[:,args.obs]
    adt.pp.merge(
        left_ad=left_ad,
        right_ad=right_ad,
        axis="obs",
        copy=False
    )
else:
    print_info("no observation transfer")

if args.var:
    print_task("variable transfer")
    right_ad.var = right_ad.var.loc[:,args.var]
    adt.pp.merge(
        left_ad=left_ad,
        right_ad=right_ad,
        axis="var",
        copy=False
    )
else:
    print_info("no variable transfer")

if args.layers:
    print_task("layer transfer")
    adt.pp.transfer_layer(
        left_ad=left_ad,
        right_ad=right_ad,
        layers=args.layers,
        copy=False
    )
else:
    print_info("no layer transfer")

if args.index:
    for idx, name in enumerate(args.index,start=1):
        left_ad.obs[name] = left_ad.obs.index.str.get(idx)
    left_ad.obs.index = left_ad.obs.index.str.get(0)

print_task("data saving")

left_ad.write_h5ad(
    filename=args.outfile if args.outfile else args.left,
    compression="gzip"
)
