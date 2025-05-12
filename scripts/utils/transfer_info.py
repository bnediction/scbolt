#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import std
import argparse
from pathlib import Path

import anndata as ad
import bonesistools as bt

parser = argparse.ArgumentParser(
    prog="info transfer",
    description="""send information (obs, var, layers) from one dataset (right) towards another dataset (left)""",
    usage="""python transfer_info.py [-h] <FILE> <FILE> --outfile <FILE> --conditions <[LITERAL ...]> --columns <COLUMN [COLUMN ...]> [OPTIONS]"""
)

parser.add_argument(
    "left",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="left-sided file (format: h5ad)"
)

parser.add_argument(
    "right",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="right-sided file (format: h5ad)"
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    default=None,
    help="output file (format: h5ad, if not specified, replace left-sided file)"
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
    type=str,
    nargs="+",
    required=False,
    default=None,
    metavar="LITERAL",
    help="name of the layers in right-sided adata.var sent to left-sided adata"
)

parser.add_argument(
    "--index",
    dest="index",
    type=str,
    nargs="+",
    required=False,
    default=None,
    metavar="LITERAL",
    help="name of the columns in [left|right] adata.obs used as index with initial index (useful when identical barcodes in index, default: None)"
)

args = parser.parse_args()

std.print_task("loading files")

std.print_info(f"loading left dataset ({args.left})")
left_ad = ad.read_h5ad(args.left)
std.print_info(f"loading right dataset ({args.right})")
right_ad = ad.read_h5ad(args.right)

if args.index:
    std.print_task("setting index")
    for adata in [left_ad, right_ad]:
        bt.sct.pp.set_index(
            adata=adata,
            keys=args.index,
            axis=0,
            copy=False
        )

if args.obs:
    std.print_task(f"transferring observations ({', '.join(map(str, args.obs))})")
    right_ad.obs = right_ad.obs.loc[:,args.obs]
    bt.sct.pp.merge(
        left_ad=left_ad,
        right_ad=right_ad,
        axis="obs",
        copy=False
    )
else:
    std.print_info("transferring observations not performed")

if args.var:
    std.print_task(f"transferring variables ({', '.join(map(str, args.var))})")
    right_ad.var = right_ad.var.loc[:,args.var]
    bt.sct.pp.merge(
        left_ad=left_ad,
        right_ad=right_ad,
        axis="var",
        copy=False
    )
else:
    std.print_info("transferring variables not performed")

if args.layers:
    std.print_task(f"transferring layers ({', '.join(map(str, args.layers))})")
    bt.sct.pp.transfer_layer(
        left_ad=left_ad,
        right_ad=right_ad,
        layers=args.layers,
        copy=False
    )
else:
    std.print_info("transferring layers not performed")

if args.index:
    for idx, name in enumerate(args.index,start=1):
        left_ad.obs[name] = left_ad.obs.index.str.get(idx)
    left_ad.obs.index = left_ad.obs.index.str.get(0)

std.print_task(f"saving data ({args.outfile})")

left_ad.write_h5ad(
    filename=args.outfile if args.outfile else args.left,
    compression="gzip"
)
