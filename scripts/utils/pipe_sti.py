#!/usr/bin/env python

import os
import std
import argparse
from pathlib import Path

import anndata as ad
import bonesistools as bt

import warnings

warnings.filterwarnings("ignore")

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="pipe_sti",
    description=(
        "Transfer columns from multiple specific adata.obs tables to an integrated "
        "adata.obs.\n"
        "Values passed to --specifics and --labels must be ordered together."
    ),
    usage=f"python {script_name} [-h] <FILE> <FILE ...> [--outfile <FILE>] --labels <LITERAL ...> --obs-label <LITERAL> [--obs <LITERAL ...>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "integrated",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input integrated dataset (format: h5ad)",
)

parser.add_argument(
    "specifics",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="input specific dataset(s) (format: h5ad)",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output integrated dataset (format: h5ad; if not specified, replace input file)",
)

parser.add_argument(
    "--labels",
    dest="labels",
    type=str,
    nargs="+",
    required=True,
    metavar="LITERAL",
    help="dataset labels ordered with --specifics",
)

parser.add_argument(
    "--obs-label",
    dest="obs_label",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in integrated adata.obs referring to dataset labels",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    nargs="+",
    required=False,
    default=None,
    metavar="LITERAL",
    help="column names in specific adata.obs tables to transfer (if not specified, transfer all columns)",
)

args = parser.parse_args()

if args.outfile is None:
    args.outfile = args.integrated

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(
    f"loading AnnData (dataset=integrated, file={std.format_path(args.integrated)})"
)
integrated_ad = ad.read_h5ad(args.integrated)

specific_ad = {}
for name, file in zip(args.labels, args.specifics):
    std.print_task(f"loading AnnData (dataset={name}, file={std.format_path(file)})")
    specific_ad[name] = ad.read_h5ad(file)

if args.obs_label not in integrated_ad.obs.columns:
    raise KeyError(f"column '{args.obs_label}' not found in integrated_ad.obs")

if args.obs is None:
    args.obs = list(integrated_ad.obs.columns)
    args.obs.remove(args.obs_label)

for column in args.obs:
    for name, adata in specific_ad.items():
        if column not in adata.obs:
            raise KeyError(f"column `{column}` not found in dataset '{name}'")

cols_to_remove = set(args.obs).intersection(set(integrated_ad.obs.columns))
if cols_to_remove:
    std.print_debug(
        "removing columns (dataset=integrated, columns={0})".format(
            "+".join(map(str, cols_to_remove))
        )
    )
    integrated_ad.obs = integrated_ad.obs.drop(list(cols_to_remove), axis=1)

std.print_task("transferring information (source=specific, target=integrated)")
bt.sct.pp.transfer_obs_sti(
    adata=integrated_ad,
    adatas=list(specific_ad.values()),
    obs=args.obs,
    conditions=args.labels,
    condition_colname=args.obs_label,
    copy=False,
)

std.print_task(
    f"saving AnnData (dataset=integrated, file={std.format_path(args.outfile)})"
)
integrated_ad.write_h5ad(filename=args.outfile, compression="gzip")
