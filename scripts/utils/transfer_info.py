#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import std
import argparse
from pathlib import Path

import anndata as ad
import bonesistools as bt


def make_composite_obs_index(adata, keys, sep="|"):
    adata.obs["_previous_index"] = adata.obs.index.astype(str)

    adata.obs.index = (
        adata.obs[["_previous_index", *keys]].astype(str).agg(sep.join, axis=1)
    )


parser = argparse.ArgumentParser(
    prog="transfer_info",
    description="""Transfer observations, variables and layers from a right dataset to a left dataset.""",
    usage="""python transfer_info.py [-h] <FILE> <FILE> [--outfile <FILE>] [--obs <LITERAL ...>] [--var <LITERAL ...>] [--layers <LITERAL ...>] [<args>]""",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "left",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input left dataset receiving information (format: h5ad)",
)

parser.add_argument(
    "right",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input right dataset providing information (format: h5ad)",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    default=None,
    help="output file storing updated left dataset (format: h5ad; if not specified, replace left file)",
)

parser.add_argument(
    "--obs",
    dest="obs",
    required=False,
    nargs="+",
    metavar="LITERAL",
    help="column names in right adata.obs transferred to left adata.obs",
)

parser.add_argument(
    "--var",
    dest="var",
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="column names in right adata.var transferred to left adata.var",
)

parser.add_argument(
    "--layers",
    dest="layers",
    type=str,
    nargs="+",
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer names in right adata.layers transferred to left adata.layers",
)

parser.add_argument(
    "--index",
    dest="index",
    type=str,
    nargs="+",
    required=False,
    default=None,
    metavar="LITERAL",
    help="adata.obs columns appended to the initial index for matching duplicated barcodes (default: None)",
)

args = parser.parse_args()

std.print_task("loading datasets")

std.print_info(f"loading left dataset from {args.left}")
left_ad = ad.read_h5ad(args.left)

std.print_info(f"loading right dataset from {args.right}")
right_ad = ad.read_h5ad(args.right)

if args.index:
    std.print_task("setting composite observation index")

    for adata in [left_ad, right_ad]:
        make_composite_obs_index(adata, args.index)

if args.obs:
    std.print_task(f"transferring observations ({', '.join(map(str, args.obs))})")

    right_ad.obs = right_ad.obs.loc[:, args.obs]
    bt.sct.pp.merge(left_ad=left_ad, right_ad=right_ad, axis="obs", copy=False)

else:
    std.print_info("transferring observations not performed")

if args.var:
    std.print_task(f"transferring variables ({', '.join(map(str, args.var))})")

    right_ad.var = right_ad.var.loc[:, args.var]
    bt.sct.pp.merge(left_ad=left_ad, right_ad=right_ad, axis="var", copy=False)

else:
    std.print_info("transferring variables not performed")

if args.layers:
    std.print_task(f"transferring layers ({', '.join(map(str, args.layers))})")

    bt.sct.pp.transfer_layer(
        left_ad=left_ad,
        right_ad=right_ad,
        layers=args.layers,
        copy=False,
    )

else:
    std.print_info("transferring layers not performed")

if args.index:
    left_ad.obs.index = left_ad.obs["_previous_index"]
    left_ad.obs.drop(columns="_previous_index", inplace=True)

std.print_task(f"saving data in {args.outfile}")

left_ad.write_h5ad(
    filename=args.outfile if args.outfile else args.left,
    compression="gzip",
)
