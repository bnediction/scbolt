#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

import anndata as ad
import pandas as pd

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="pipe_sti",
    description=(
        "Transfer columns from multiple specific adata.obs tables to an integrated "
        "adata.obs.\n"
        "Values passed to --specifics and --labels must be ordered together."
    ),
    usage=f"python {script_name} [-h] <FILE> <FILE ...> [--outfile <FILE>] --labels <LITERAL ...> --obs-label <LITERAL> [--obs <LITERAL ...>]",
    formatter_class=cli.HelpFormatter,
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
    help=(
        "output integrated dataset (format: h5ad; if not specified, replace input "
        "file)"
    ),
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
    help=(
        "column names in specific adata.obs tables to transfer (if not specified, "
        "transfer all columns)"
    ),
)

args = parser.parse_args()


def reindex_boolean_series(series, target_index):
    values = pd.Series(False, index=target_index, dtype=bool)
    aligned = series.reindex(target_index)
    present = aligned.notna()
    values.loc[present] = aligned.loc[present].astype(bool)
    return values


def transfer_dataframe_columns(source, target_index, columns):
    values = source[columns].reindex(target_index)

    for column in columns:
        source_column = source[column]
        if pd.api.types.is_bool_dtype(source_column):
            values[column] = reindex_boolean_series(source_column, target_index)

    return values


def remove_index_prefix(index, sep=":"):
    return pd.Index([str(value).split(sep, 1)[-1] for value in index], name="barcode")


def transfer_obs_columns(source, target_index, columns, source_label, target_label):
    source_index = pd.Index(source.obs_names.astype(str), name="barcode")

    if source_index.has_duplicates:
        duplicates = source_index[source_index.duplicated()].unique()
        raise ValueError(
            "duplicated observation transfer keys in specific dataset "
            f"(label={source_label}, keys={'+'.join(map(str, duplicates[:5]))})"
        )

    missing = target_index[~target_index.isin(source_index)]
    if len(missing) > 0:
        raise KeyError(
            "observations not found in specific dataset "
            f"(label={target_label}, keys={'+'.join(map(str, missing[:5]))})"
        )

    source_obs = source.obs.copy()
    source_obs.index = source_index
    return transfer_dataframe_columns(source_obs, target_index, columns)


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

for column in args.obs:
    if all(
        pd.api.types.is_bool_dtype(adata.obs[column]) for adata in specific_ad.values()
    ):
        integrated_ad.obs[column] = pd.Series(
            False,
            index=integrated_ad.obs.index,
            dtype=bool,
        )

std.print_task("transferring information (source=specific, target=integrated)")
for name, adata in specific_ad.items():
    mask = integrated_ad.obs[args.obs_label] == name
    target_rows = integrated_ad.obs.index[mask.to_numpy()]
    target_index = remove_index_prefix(target_rows)
    transferred_obs = transfer_obs_columns(
        source=adata,
        target_index=target_index,
        columns=args.obs,
        source_label=name,
        target_label=name,
    )
    transferred_obs.index = target_rows

    for column in args.obs:
        integrated_ad.obs.loc[target_rows, column] = transferred_obs[column]

std.print_task(
    f"saving AnnData (dataset=integrated, file={std.format_path(args.outfile)})"
)
std.write_h5ad(integrated_ad, filename=args.outfile, compression="gzip")
