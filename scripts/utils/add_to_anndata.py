#!/usr/bin/env python

from typing import Sequence, Union, cast
from pathlib import Path

import std
import argparse
import cli

import pandas as pd
import anndata as ad

PathLike = Union[str, Path]
category = pd.Categorical


def generate_unique_index_name(
    dfs: Union[pd.DataFrame, Sequence[pd.DataFrame]],
    base: str = "index",
) -> str:
    dfs = [dfs] if isinstance(dfs, pd.DataFrame) else dfs
    column_names = set()
    for df in dfs:
        column_names.update(set(df.columns))
    index_name = base
    _i = 0
    while index_name in column_names:
        index_name = f"{base}_{_i}"
        _i += 1
    return index_name


def add_label_prefix(values: pd.Series, label: str) -> pd.Series:
    values = values.astype(object)
    return values.where(values.isna(), label + "_" + values.astype(str))


def strip_label_prefix(value: object, label: object) -> str:
    text = str(value)
    prefix = f"{label}:"
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="add_to_anndata",
    description=(
        "Add CSV/TSV file content to an AnnData file. The content can be added "
        "either to 'adata.obs' or 'adata.var', depending on --axis."
    ),
    usage=f"python {script_name} <FILE> <FILE> --csv <FILE> [--axis <AXIS>] [<args>]",
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file (format: h5ad or loom)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file (format: h5ad or loom)",
)

parser.add_argument(
    "--csv",
    dest="csv",
    type=lambda x: Path(x).resolve(),
    nargs="+",
    required=True,
    metavar="FILE",
    help="file(s) whose content is added to AnnData (format: CSV or TSV)",
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
    help="dataset labels ordered with --csv values (required when multiple files are passed to --csv)",
)

parser.add_argument(
    "--label-column",
    dest="label_column",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="column name in adata.obs distinguishing samples (required when multiple files are passed to --csv, default: None)",
)

parser.add_argument(
    "--add-prefix",
    dest="add_prefix",
    type=str,
    nargs="+",
    required=False,
    default=[],
    metavar="LITERAL",
    help="dataframe columns whose values receive the dataset label as prefix (not allowed with a single --csv file, default: None)",
)

parser.add_argument(
    "--axis",
    dest="axis",
    action=cli.Store_axis,
    required=False,
    default="0",
    help="AnnData axis where CSV/TSV content is added (0/obs or 1/var, default: obs)",
)

parser.add_argument(
    "--sep",
    dest="sep",
    type=str,
    required=False,
    default=",",
    metavar="CHAR",
    help="field delimiter for CSV/TSV files (default: ',')",
)

parser.add_argument(
    "--index",
    dest="index",
    type=int,
    required=False,
    default=0,
    metavar="INT",
    help="column index in CSV/TSV files referring to features or barcodes (default: 0)",
)

parser.add_argument(
    "--type",
    dest="type",
    action=cli.Store_type,
    required=False,
    default=None,
    help="dataframe value type (expected: str, int, float, complex, bool, category; default: None)",
)

parser.add_argument(
    "--plot-obs",
    dest="plot_obs",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="observation column to plot after adding tabular annotations (default: None)",
)

parser.add_argument(
    "--plot-representation",
    dest="plot_representation",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="embedding representation in adata.obsm used by --plot-obs (default: None)",
)

parser.add_argument(
    "--plot-outfile",
    dest="plot_outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output PDF file written by --plot-obs (default: None)",
)

args = parser.parse_args()

plot_args = [args.plot_obs, args.plot_representation, args.plot_outfile]
if any(value is not None for value in plot_args) and not all(
    value is not None for value in plot_args
):
    raise argparse.ArgumentError(
        None,
        "options --plot-obs, --plot-representation and --plot-outfile "
        "must be passed together",
    )

if len(args.csv) == 1:
    if args.labels is not None:
        raise argparse.ArgumentError(
            None, "option --labels not allowed when single value passed to option --csv"
        )
    elif args.label_column is not None:
        raise argparse.ArgumentError(
            None,
            "option --label-column not allowed when single value passed to option --csv",
        )
    if args.add_prefix:
        raise argparse.ArgumentError(
            None,
            "option --add-prefix not allowed when single value passed to option --csv",
        )
    else:
        args.add_prefix = None
else:
    if args.labels is None:
        raise argparse.ArgumentError(
            None, "option --labels required when multiple values passed to option --csv"
        )
    elif len(args.labels) != len(args.csv):
        raise argparse.ArgumentError(
            None, "options --csv and --labels requires same number of passed values"
        )
    elif args.label_column is None:
        raise argparse.ArgumentError(
            None,
            "option --label-column required when multiple values passed to option --csv",
        )
    labels = cast(Sequence[str], args.labels)
    label_column = cast(str, args.label_column)

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")
if str(args.infile).endswith("h5ad"):
    adata = ad.read_h5ad(filename=args.infile)
elif str(args.infile).endswith("loom"):
    adata = ad.read_loom(filename=args.infile)
else:
    raise argparse.ArgumentError(
        None, "unable to synchronously open infile (required format: h5ad or loom)"
    )

if len(args.csv) == 1:
    std.print_task(f"loading tabular annotation (file={std.format_path(args.csv[0])})")
    df = pd.read_csv(
        args.csv[0],
        sep=args.sep,
        index_col=args.index,
    ).astype(args.type)
    if args.axis in [0, "obs"]:
        cols_to_remove = set(adata.obs.columns) & set(df.columns)
        if cols_to_remove:
            std.print_debug(
                "removing columns (table=adata.obs, columns={0})".format(
                    "+".join(map(str, cols_to_remove))
                )
            )
            adata.obs = adata.obs.drop(list(cols_to_remove), axis=1)
        adata.obs = adata.obs.merge(
            right=df, how="left", left_index=True, right_index=True
        )
    else:
        cols_to_remove = set(adata.var.columns) & set(df.columns)
        if cols_to_remove:
            std.print_debug(
                "removing columns (table=adata.var, columns={0})".format(
                    "+".join(map(str, cols_to_remove))
                )
            )
            adata.var = adata.var.drop(list(cols_to_remove), axis=1)
        adata.var = adata.var.merge(
            right=df, how="left", left_index=True, right_index=True
        )
else:
    std.print_task(
        "loading tabular annotations "
        f"(files={', '.join(std.format_path(file) for file in args.csv)})"
    )
    dfs = dict()
    add_prefix = args.add_prefix or []
    for name, file in zip(labels, args.csv):
        df = pd.read_csv(file, sep=args.sep, index_col=args.index).astype(args.type)
        for col in add_prefix:
            df[col] = add_label_prefix(df[col], name)
            if args.type == "category":
                df[col] = df[col].astype("category")
        dfs[name] = df.copy(deep=True)
    for name, df in dfs.items():
        df[label_column] = name
    csv_df = pd.concat(dfs.values(), axis=0)
    del df, dfs
    value_columns = [column for column in csv_df.columns if column != label_column]
    if args.axis in [0, "obs"]:
        adata_df = adata.obs.copy()
        cols_to_remove = set(adata_df.columns) & set(csv_df.columns) - set(
            [label_column]
        )
        if cols_to_remove:
            std.print_debug(
                "removing columns (table=adata.obs, columns={0})".format(
                    "+".join(map(str, cols_to_remove))
                )
            )
            adata_df = adata_df.drop(list(cols_to_remove), axis=1)
    else:
        adata_df = adata.var.copy()
        cols_to_remove = set(adata_df.columns) & set(csv_df.columns) - set(
            [label_column]
        )
        if cols_to_remove:
            std.print_debug(
                "removing columns (table=adata.var, columns={0})".format(
                    "+".join(map(str, cols_to_remove))
                )
            )
            adata_df = adata_df.drop(list(cols_to_remove), axis=1)
    index_name = generate_unique_index_name([csv_df, adata_df])
    original_index_name = generate_unique_index_name(
        [csv_df, adata_df],
        base=f"{index_name}_original",
    )
    csv_df[index_name] = csv_df.index
    csv_df.set_index([index_name, label_column], inplace=True)
    adata_df[original_index_name] = adata_df.index
    adata_df[index_name] = adata_df.index
    if args.axis in [0, "obs"]:
        adata_df[index_name] = [
            strip_label_prefix(index, label)
            for index, label in zip(adata_df[index_name], adata_df[label_column])
        ]
    adata_df.set_index([index_name, label_column], inplace=True)
    adata_df = adata_df.merge(
        right=csv_df, how="left", left_index=True, right_index=True
    )
    adata_df.reset_index(level=(label_column,), inplace=True)
    adata_df.index = adata_df[original_index_name]
    adata_df.drop(columns=[original_index_name], inplace=True)
    adata_df.index.name = None
    if args.type is not None:
        for column in value_columns:
            if column in adata_df.columns:
                adata_df[column] = adata_df[column].astype(args.type)
    if args.axis in [0, "obs"]:
        adata.obs = adata_df
    else:
        adata.var = adata_df

if args.plot_obs:
    std.print_task(f"plotting embeddings (file={std.format_path(args.plot_outfile)})")
    std.plot_categorical_embedding(
        adata,
        obs=args.plot_obs,
        embedding=args.plot_representation,
        label=std.format_embedding(args.plot_representation),
        outfile=args.plot_outfile,
    )

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
if str(args.outfile).endswith("h5ad"):
    std.write_h5ad(adata, filename=args.outfile, compression="gzip")
elif str(args.outfile).endswith("loom"):
    adata.write_loom(filename=args.outfile, write_obsm_varm=True)
else:
    raise argparse.ArgumentError(
        None, "unable to synchronously create outfile (required format: h5ad or loom)"
    )
