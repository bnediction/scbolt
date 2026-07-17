#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

import anndata as ad
import bonesistools as bt
import pandas as pd

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="pipe_its",
    description=(
        "Transfer columns from an integrated adata.obs to multiple specific "
        "adata.obs and adata.var tables.\n"
        "Values passed to --specifics and --labels must be ordered together.\n"
        "If --outfiles is specified, values must also be ordered with --specifics "
        "and --labels."
    ),
    usage=(
        f"python {script_name} [-h] <FILE> <FILE ...> [--outfiles <FILE ...>] "
        "--labels <LITERAL ...> --obs-label <LITERAL> "
        "[--obs <LITERAL ...>] [--var <LITERAL ...>]"
    ),
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
    "--outfiles",
    dest="outfiles",
    type=lambda x: Path(x).resolve(),
    nargs="+",
    required=False,
    default=None,
    metavar="FILE",
    help=(
        "output specific dataset(s) (format: h5ad; if not specified, replace input "
        "files)"
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
        "column names in integrated adata.obs to transfer (if not specified, transfer "
        "all columns)"
    ),
)

parser.add_argument(
    "--var",
    dest="var",
    type=str,
    nargs="+",
    required=False,
    default=None,
    metavar="LITERAL",
    help="column names in integrated adata.var to transfer",
)

parser.add_argument(
    "--plot-obs",
    dest="plot_obs",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="if specified, plot transferred observation labels",
)

parser.add_argument(
    "--embedding",
    dest="embedding",
    type=str,
    required=False,
    default="X_umap",
    metavar="LITERAL",
    help="embedding representation used for label plotting (default: X_umap)",
)

args = parser.parse_args()

std.set_default_plot_params(bt.omics.pl)


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


def remove_obs_name_prefix(adata, sep=":"):
    obs_names = pd.Index(
        [str(obs_name).split(sep, 1)[-1] for obs_name in adata.obs_names],
        name=adata.obs.index.name,
    )
    adata.obs.index = obs_names


def plot_labels(adata, obs: str, embedding: str, outfile: Path) -> None:
    std.plot_categorical_embedding(
        adata,
        obs=obs,
        embedding=embedding,
        outfile=outfile,
    )


def transfer_obs_columns(source, target, columns, source_label, target_label):
    source_index = pd.Index(source.obs_names.astype(str), name="barcode")
    target_index = pd.Index(target.obs_names.astype(str), name="barcode")

    if source_index.has_duplicates:
        duplicates = source_index[source_index.duplicated()].unique()
        raise ValueError(
            "duplicated observation transfer keys in integrated dataset "
            f"(label={source_label}, keys={'+'.join(map(str, duplicates[:5]))})"
        )

    missing = target_index[~target_index.isin(source_index)]
    if len(missing) > 0:
        raise KeyError(
            "observations not found in integrated dataset "
            f"(label={target_label}, keys={'+'.join(map(str, missing[:5]))})"
        )

    source_obs = source.obs.copy()
    source_obs.index = source_index
    values = transfer_dataframe_columns(source_obs, target_index, columns)
    values.index = target.obs.index
    return values


if args.outfiles is None:
    args.outfiles = args.specifics

for outfile in args.outfiles:
    if not Path(os.path.dirname(outfile)).exists():
        os.makedirs(Path(os.path.dirname(outfile)))

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
    if column not in integrated_ad.obs:
        raise KeyError(f"column `{column}` not found in dataset 'integrated'")

if args.var is not None:
    for column in args.var:
        if column not in integrated_ad.var:
            raise KeyError(f"column `{column}` not found in integrated_ad.var")

std.print_task("transferring observations (source=integrated, target=specific)")
for name, adata in specific_ad.items():
    source_ad = integrated_ad[integrated_ad.obs[args.obs_label] == name].copy()
    remove_obs_name_prefix(source_ad)
    transferred_obs = transfer_obs_columns(
        source=source_ad,
        target=adata,
        columns=args.obs,
        source_label=name,
        target_label=name,
    )

    cols_to_remove = set(args.obs).intersection(set(adata.obs.columns))
    if cols_to_remove:
        std.print_debug(
            "removing columns (dataset={0}, columns={1})".format(
                name, "+".join(map(str, cols_to_remove))
            )
        )
        adata.obs = adata.obs.drop(list(cols_to_remove), axis=1)
    adata.obs = adata.obs.join(transferred_obs, how="left")

if args.var is not None:
    std.print_task("transferring variables (source=integrated, target=specific)")
    for name, adata in specific_ad.items():
        cols_to_remove = set(args.var).intersection(set(adata.var.columns))
        if cols_to_remove:
            std.print_debug(
                "removing columns (dataset={0}, columns={1})".format(
                    name, "+".join(map(str, cols_to_remove))
                )
            )
            adata.var = adata.var.drop(list(cols_to_remove), axis=1)
        adata.var = adata.var.join(
            transfer_dataframe_columns(
                source=integrated_ad.var,
                target_index=adata.var.index,
                columns=args.var,
            ),
            how="left",
        )

for name, outfile in zip(args.labels, args.outfiles):
    if args.plot_obs is not None:
        labels_plot = Path(os.path.dirname(outfile)) / "labels.pdf"
        std.print_task(
            f"plotting embeddings (dataset={name}, file={std.format_path(labels_plot)})"
        )
        plot_labels(
            specific_ad[name],
            obs=args.plot_obs,
            embedding=args.embedding,
            outfile=labels_plot,
        )

    std.print_task(f"saving AnnData (dataset={name}, file={std.format_path(outfile)})")
    std.write_h5ad(specific_ad[name], filename=outfile, compression="gzip")
