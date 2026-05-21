#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import anndata as ad
import bonesistools as bt

parser = argparse.ArgumentParser(
    prog="pipe_sti",
    description="""
    Send information from multiple specific 'adata.obs' towards integrated 'adata.obs', first ones referring to a name. \
    Values passed to parameters '--specifics' and '--names' have to be ordered together.
    """,
    usage="python pipe_sti.py <FILE> <FILE ...> [--outfiles <FILE ...>] --labels <LITERAL ...> --column-label <LITERAL> --obs <LITERAL ...>",
)

parser.add_argument(
    "integrated",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input integration-based file (format: h5ad)",
)

parser.add_argument(
    "specifics",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="input condition-based input file(s) (format: h5ad)",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="condition-based output file(s) (format: h5ad, if not specified, replace input file)",
)

parser.add_argument(
    "--labels",
    dest="labels",
    type=str,
    nargs="+",
    required=True,
    metavar="LITERAL",
    help="dataset names (ordered with parameter --specifics)",
)

parser.add_argument(
    "--obs-label",
    dest="obs_label",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in integrated 'adata.obs' referring to dataset names",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    nargs="+",
    required=False,
    default=None,
    metavar="LITERAL",
    help="column names in integrated 'adata.obs' to transfer (if not specified, transfer all columns)",
)

args = parser.parse_args()

if args.outfile is None:
    args.outfile = args.integrated

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading dataset 'integrated' from {str(args.integrated)}")
integrated_ad = ad.read_h5ad(args.integrated)

specific_ad = {}
for name, file in zip(args.labels, args.specifics):
    std.print_task(f"loading dataset '{name}' from {str(file)}")
    specific_ad[name] = ad.read_h5ad(file)

if args.obs_label not in integrated_ad.obs.columns:
    raise KeyError(f"column '{args.obs_label}' not found in integrated_ad.obs")

for column in args.obs:
    for name, adata in specific_ad.items():
        if column not in adata.obs:
            raise KeyError(f"column `{column}` not found in dataset '{name}'")

if args.obs is None:
    args.obs = list(integrated_ad.obs.columns)
    args.obs.remove(args.obs_label)

cols_to_remove = set(args.obs).intersection(set(integrated_ad.obs.columns))
if cols_to_remove:
    std.print_debug(
        "removing in dataset 'integrated' the following column(s): {1}".format(
            name, ", ".join(f"'{cols}'" for cols in cols_to_remove)
        )
    )
    integrated_ad.obs = integrated_ad.obs.drop(cols_to_remove, axis=1)

std.print_task("transferring information from specific datasets to integrated datasets")
bt.sct.pp.transfer_obs_sti(
    adata=integrated_ad,
    adatas=list(specific_ad.values()),
    obs=args.obs,
    conditions=args.labels,
    condition_colname=args.obs_label,
    copy=False,
)

std.print_task(f"saving dataset 'integrated' in {str(args.outfile)}")
integrated_ad.write_h5ad(filename=args.outfile, compression="gzip")
