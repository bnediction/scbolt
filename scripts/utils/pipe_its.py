#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import anndata as ad

parser = argparse.ArgumentParser(
    prog="pipe_its",
    description=(
        "Transfer columns from an integrated adata.obs to multiple specific "
        "adata.obs tables.\n"
        "Values passed to --specifics and --labels must be ordered together.\n"
        "If --outfiles is specified, values must also be ordered with --specifics "
        "and --labels."
    ),
    usage="""python pipe_its.py [-h] <FILE> <FILE ...> [--outfiles <FILE ...>] --labels <LITERAL ...> --obs-label <LITERAL> [--obs <LITERAL ...>]""",
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
    "--outfiles",
    dest="outfiles",
    type=lambda x: Path(x).resolve(),
    nargs="+",
    required=False,
    default=None,
    metavar="FILE",
    help="output specific dataset(s) (format: h5ad; if not specified, replace input files)",
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
    help="column names in integrated adata.obs to transfer (if not specified, transfer all columns)",
)

args = parser.parse_args()

if args.outfiles is None:
    args.outfiles = args.specifics

for outfile in args.outfiles:
    if not Path(os.path.dirname(outfile)).exists():
        os.makedirs(Path(os.path.dirname(outfile)))

std.print_task(f"loading dataset 'integrated' from {str(args.integrated)}")
integrated_ad = ad.read_h5ad(args.integrated)

specific_ad = {}
for name, file in zip(args.labels, args.specifics):
    std.print_task(f"loading dataset '{name}' from {str(file)}")
    specific_ad[name] = ad.read_h5ad(file)

if args.obs_label not in integrated_ad.obs.columns:
    raise KeyError(f"column '{args.obs_label}' not found in integrated_ad.obs")

if args.obs is None:
    args.obs = list(integrated_ad.obs.columns)
    args.obs.remove(args.obs_label)

for column in args.obs:
    if column not in integrated_ad.obs:
        raise KeyError(f"column `{column}` not found in dataset 'integrated'")

std.print_task("transferring information from integrated dataset to specific datasets")
for name, adata in specific_ad.items():
    cols_to_remove = set(args.obs).intersection(set(adata.obs.columns))
    if cols_to_remove:
        std.print_debug(
            "removing in dataset '{0}' the following column(s): {1}".format(
                name, ", ".join(f"'{cols}'" for cols in cols_to_remove)
            )
        )
        adata.obs = adata.obs.drop(list(cols_to_remove), axis=1)
    adata.obs = adata.obs.merge(
        right=integrated_ad[integrated_ad.obs[args.obs_label] == name].obs[args.obs],
        how="left",
        left_index=True,
        right_index=True,
    )

for name, outfile in zip(args.labels, args.outfiles):
    std.print_task(f"saving dataset '{name}' in {str(outfile)}")
    specific_ad[name].write_h5ad(filename=outfile, compression="gzip")
