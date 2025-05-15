#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

from typing import Union
from pathlib import Path

import std
import argparse, cli

import pandas as pd
import anndata as ad

PathLike = Union[str,Path]
category = pd.Categorical

parser = argparse.ArgumentParser(
    prog="add_to_anndata",
    description=
    """
    Add csv/tsv file content to h5ad file. The content can be added either \
    to 'adata.obs' or 'adata.var', depending on value passed to option --axis.
    """,
    usage="python add_to_anndata.py <FILE> <FILE> --csv <FILE> [--axis <AXIS>] [<args>]",
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file (format: loom, h5ad)"
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file (format: loom, h5ad)"
)

parser.add_argument(
    "--csv",
    dest="csv",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="file whose content is added to 'adata' (format: csv, tsv)"
)

parser.add_argument(
    "--axis",
    dest="axis",
    action=cli.Store_axis,
    required=False,
    default="0",
    help="axis in 'adata' where csv/tsv file content is added"
)

parser.add_argument(
    "--sep",
    dest="sep",
    type=str,
    required=False,
    default=",",
    metavar="CHAR",
    help="field delimiter for csv format (default: ',')"
)

parser.add_argument(
    "--index",
    dest="index",
    type=int,
    required=False,
    default=0,
    metavar="INT",
    help="column index in csv/tsv file referring to features or barcodes (defaut: 0)"
)

parser.add_argument(
    "--type",
    dest="type",
    action=cli.Store_type,
    required=False,
    default=str,
    help="dataframe type (expected: str, int, float, complex, bool, category; default: str)"
)

args = parser.parse_args()

if str(args.infile).endswith("h5ad"):
    adata = ad.read_h5ad(filename=args.infile)
elif str(args.infile).endswith("loom"):
    adata = ad.read_loom(filename=args.infile)
else:
    raise argparse.ArgumentError("unable to synchronously open infile (required format: h5ad or loom)")

df = pd.read_csv(
    args.csv,
    sep=args.sep,
    index_col=args.index,
    dtype=args.type
)

if args.axis in [0, "obs"]:
    cols_to_remove = set(adata.obs.columns).intersection(set(df.columns))
    if cols_to_remove:
        std.print_debug("removing in 'adata.obs' the following column(s): {0}".format(', '.join(f"'{cols}'" for cols in cols_to_remove)))
        adata.obs = adata.obs.drop(cols_to_remove, axis=1)
    adata.obs = adata.obs.merge(
        how="left",
        right=df,
        left_index=True,
        right_index=True
    )
else:
    cols_to_remove = set(adata.var.columns).intersection(set(df.columns))
    if cols_to_remove:
        std.print_debug("removing in 'adata.var' the following column(s): {1}".format(', '.join(f"'{cols}'" for cols in cols_to_remove)))
        adata.var = adata.var.drop(cols_to_remove, axis=1)
    adata.var = adata.var.merge(
        how="left",
        right=df,
        left_index=True,
        right_index=True
    )

if str(args.outfile).endswith("h5ad"):
    adata.write_h5ad(filename=args.outfile, compression="gzip")
elif str(args.outfile).endswith("loom"):
    adata.write_loom(filename=args.outfile, write_obsm_varm=True)
else:
    raise argparse.ArgumentError("unable to synchronously create outfile (required format: h5ad or loom)")
