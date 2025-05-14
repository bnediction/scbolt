#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import anndata as ad

parser = argparse.ArgumentParser(
    prog="pipe_its",
    description="""
    Send information from integrated 'adata.obs' towards multiple specific 'adata.obs', each one referring to a name. \
    Values passed to parameters '--specifics' and '--names' have to be ordered together. \
    If parameter '--outfiles' is specified, it also have to be specified in the same order as '--specifics' and '--names'.
    """,
    usage="""python pipe_its.py [-h] <FILE> <FILE ...> [--outfiles <FILE ...>] --labels <LITERAL ...> --column-label <LITERAL> --obs <LITERAL ...>"""
)

parser.add_argument(
    "integrated",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input integration-based file (format: h5ad)"
)

parser.add_argument(
    "specifics",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="input condition-based input file(s) (format: h5ad)"
)

parser.add_argument(
    "--outfiles",
    dest="outfiles",
    type=lambda x: Path(x).resolve(),
    nargs="+",
    required=False,
    default=None,
    metavar="FILE",
    help="condition-based output file(s) (format: h5ad. If not specified, replace input file(s))"
)

parser.add_argument(
    "--labels",
    dest="labels",
    type=str,
    nargs="+",
    required=True,
    metavar="LITERAL",
    help="dataset names (ordered with parameter --specifics)"
)

parser.add_argument(
    "--obs-label",
    dest="obs_label",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in integrated 'adata.obs' referring to dataset names"
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    nargs="+",
    required=False,
    default=None,
    metavar="LITERAL",
    help="column names in integrated 'adata.obs' to transfer (if not specified, transfer all columns)"
)

args = parser.parse_args()

if args.outfiles is None:
    args.outfiles = args.specifics

for outfile in args.outfiles:
    if not Path(os.path.dirname(outfile)).exists():
        os.makedirs(Path(os.path.dirname(outfile)))

std.print_task(f"loading dataset 'integrated' ({str(args.integrated)})")
integrated_ad = ad.read_h5ad(args.integrated)

specific_ad = {}
for name, file in zip(args.labels, args.specifics):
    std.print_task(f"loading dataset '{name}' ({str(file)})")
    specific_ad[name] = ad.read_h5ad(file)

if args.obs_label not in integrated_ad.obs.columns:
    raise KeyError(f"column '{args.obs_label}' not found in integrated_ad.obs")

for column in args.obs:
    if column not in integrated_ad.obs:
        raise KeyError(f"column `{column}` not found in dataset 'integrated'")

if args.obs is None:
    args.obs = list(integrated_ad.obs.columns)
    args.obs.remove(args.obs_label)

std.print_task("transferring information from integrated dataset to specific datasets")
for name, adata in specific_ad.items():
    cols_to_remove = set(args.obs).intersection(set(adata.obs.columns))
    if cols_to_remove:
        std.print_debug("removing in dataset '{0}' the following column(s): {1}".format(name,', '.join(f"'{cols}'" for cols in cols_to_remove)))
        adata.obs = adata.obs.drop(cols_to_remove, axis=1)
    adata.obs = adata.obs.merge(
        right=integrated_ad[integrated_ad.obs[args.obs_label] == name].obs[args.obs],
        how="left",
        left_index=True,
        right_index=True
    )

for name, outfile in zip(args.labels, args.outfiles):
    std.print_task(f"saving dataset '{name}' in {str(file)}")
    specific_ad[name].write_h5ad(
        filename=outfile,
        compression="gzip"
    )
