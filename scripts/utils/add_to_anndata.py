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

def generate_unique_index_name(
    dfs: Union[pd.DataFrame]
) -> str:
    dfs = [dfs] if isinstance(dfs, pd.DataFrame) else dfs
    column_names = set()
    for df in dfs:
        column_names.update(set(df.columns))
    index_name = "index"
    _i = 0
    while index_name in column_names:
        index_name = f"index_{_i}"
        _i += 1
    return index_name

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
    nargs="+",
    required=True,
    help="file(s) whose content is added to 'adata' (format: csv, tsv)"
)

parser.add_argument(
    "--labels",
    dest="labels",
    action=cli.Required_length,
    type=str,
    min=2,
    required=False,
    default=None,
    metavar="LITERAL",
    help="labels related to each dataset (ordered with passed values in --csv, required when multiple infiles)",
)

parser.add_argument(
    "--label-column",
    dest="label_column",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="column name such as adata.obs['LITERAL'] distinguishes samples (default: None, required when multiple infiles)"
)

parser.add_argument(
    "--add-prefix",
    dest="add_prefix",
    type=str,
    nargs="+",
    required=False,
    default=[],
    metavar="LITERAL",
    help="column names in dataframe for which the label is added as a prefix (default: None, not allowed when single value passed to option --csv)"
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
    default=None,
    help="dataframe type (expected: str, int, float, complex, bool, category; default: None)"
)

args = parser.parse_args()

if len(args.csv) == 1:
    if args.labels is not None:
        raise argparse.ArgumentError(None, "option --labels not allowed when single value passed to option --csv")
    elif args.label_column is not None:
        raise argparse.ArgumentError(None, "option --label-column not allowed when single value passed to option --csv")
    if args.add_prefix:
        raise argparse.ArgumentError(None, "option --add-prefix not allowed when single value passed to option --csv")
    else:
        args.add_prefix = None
else:
    if args.labels is None:
        raise argparse.ArgumentError(None, "option --labels required when multiple values passed to option --csv")
    elif len(args.labels) != len(args.csv):
        raise argparse.ArgumentError(None, "options --csv and --labels requires same number of passed values")
    elif args.label_column is None:
        raise argparse.ArgumentError(None, "option --label-column required when multiple values passed to option --csv")

if str(args.infile).endswith("h5ad"):
    adata = ad.read_h5ad(filename=args.infile)
elif str(args.infile).endswith("loom"):
    adata = ad.read_loom(filename=args.infile)
else:
    raise argparse.ArgumentError(None, "unable to synchronously open infile (required format: h5ad or loom)")

if len(args.csv) == 1:
    df = pd.read_csv(
        args.csv[0],
        sep=args.sep,
        index_col=args.index,
    ).astype(args.type)
    if args.axis in [0, "obs"]:
        cols_to_remove = set(adata.obs.columns) & set(df.columns)
        if cols_to_remove:
            std.print_debug("removing in 'adata.obs' the following column(s): {0}".format(', '.join(f"'{cols}'" for cols in cols_to_remove)))
            adata.obs = adata.obs.drop(cols_to_remove, axis=1)
        adata.obs = adata.obs.merge(
            right=df,
            how="left",
            left_index=True,
            right_index=True
        )
    else:
        cols_to_remove = set(adata.var.columns) & set(df.columns)
        if cols_to_remove:
            std.print_debug("removing in 'adata.var' the following column(s): {1}".format(', '.join(f"'{cols}'" for cols in cols_to_remove)))
            adata.var = adata.var.drop(cols_to_remove, axis=1)
        adata.var = adata.var.merge(
            right=df,
            how="left",
            left_index=True,
            right_index=True
        )
else:
    dfs = dict()
    for name, file in zip(args.labels, args.csv):
        df = pd.read_csv(
            file,
            sep=args.sep,
            index_col=args.index
        ).astype(args.type)
        for col in args.add_prefix:
            df[col] = df[col].apply(lambda x: f"{name}_{x}")
        dfs[name] = df.copy(deep=True)
        for name, df in dfs.items():
            df[args.label_column] = name
        csv_df = pd.concat(dfs.values(), axis=0)
    del df, dfs
    if args.axis in [0, "obs"]:
        adata_df = adata.obs.copy()
        cols_to_remove = set(adata_df.columns) & set(csv_df.columns) - set([args.label_column])
        if cols_to_remove:
            std.print_debug("removing in 'adata.obs' the following column(s): {0}".format(', '.join(f"'{cols}'" for cols in cols_to_remove)))
            adata_df = adata_df.drop(cols_to_remove, axis=1)
    else:
        adata_df = adata.var.copy()
        cols_to_remove = set(adata_df.columns) & set(csv_df.columns) - set([args.label_column])
        if cols_to_remove:
            std.print_debug("removing in 'adata.var' the following column(s): {0}".format(', '.join(f"'{cols}'" for cols in cols_to_remove)))
            adata_df = adata_df.drop(cols_to_remove, axis=1)
    index_name = generate_unique_index_name([csv_df, adata_df])
    csv_df[index_name] = csv_df.index
    csv_df.set_index([index_name, args.label_column], inplace=True)
    adata_df[index_name] = adata_df.index
    adata_df.set_index([index_name, args.label_column], inplace=True)
    adata_df = adata_df.merge(
        right=csv_df,
        how="left",
        left_index=True,
        right_index=True
    )
    adata_df.reset_index(
        level=(args.label_column,),
        inplace=True
    )
    adata_df.index.name = None
    if args.axis in [0, "obs"]:
        adata.obs = adata_df
    else:
        adata.var = adata_df

if str(args.outfile).endswith("h5ad"):
    adata.write_h5ad(filename=args.outfile, compression="gzip")
elif str(args.outfile).endswith("loom"):
    adata.write_loom(filename=args.outfile, write_obsm_varm=True)
else:
    raise argparse.ArgumentError("unable to synchronously create outfile (required format: h5ad or loom)")
