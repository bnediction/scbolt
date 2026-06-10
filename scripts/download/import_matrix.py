#!/usr/bin/env python

import argparse
import gzip
import warnings
from pathlib import Path

import anndata as ad
from anndata import utils as ad_utils
import bonesistools as bt
import pandas as pd
import scipy.io

import std

script_name = Path(__file__).name


def read_table(path: Path) -> pd.DataFrame:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as handle:
        return pd.read_csv(handle, sep="\t", header=None, dtype=str)


def make_var(features: pd.DataFrame) -> pd.DataFrame:
    symbols = (
        features.iloc[:, 1]
        if features.shape[1] > 1
        else features.iloc[:, 0]
    ).astype(str)
    var_names = pd.Index(symbols, name=None)
    var_names.name = None
    var = pd.DataFrame(
        index=var_names,
    )
    var["Accession"] = features.iloc[:, 0].astype(str).to_numpy()
    var["symbol"] = symbols.to_numpy()
    return var


parser = argparse.ArgumentParser(
    prog="import_matrix",
    description="Import a public 10x-style count matrix into AnnData.",
    usage=(
        f"python {script_name} <FILE> <FILE> <FILE> <FILE> "
        "[--gsm <GSM>]"
    ),
)

parser.add_argument("matrix", type=lambda x: Path(x).resolve(), metavar="FILE")
parser.add_argument("barcodes", type=lambda x: Path(x).resolve(), metavar="FILE")
parser.add_argument("features", type=lambda x: Path(x).resolve(), metavar="FILE")
parser.add_argument("outfile", type=lambda x: Path(x).resolve(), metavar="FILE")
parser.add_argument("--gsm", default=None, metavar="GSM")

args = parser.parse_args()

std.print_info(
    f"loading Matrix Market exchange counts (file={std.format_path(args.matrix)})"
)
counts = scipy.io.mmread(args.matrix).tocsr()

std.print_info(f"loading barcodes (file={std.format_path(args.barcodes)})")
obs_names = pd.Index(
    read_table(args.barcodes).iloc[:, 0].astype(str),
    name=None,
)
obs_names = ad_utils.make_index_unique(obs_names)
obs_names.name = None

std.print_info(f"loading feature annotations (file={std.format_path(args.features)})")
var = make_var(read_table(args.features))

if counts.shape == (len(var), len(obs_names)):
    counts = counts.T.tocsr()
elif counts.shape != (len(obs_names), len(var)):
    raise ValueError(
        "matrix shape is incompatible with barcodes and genes "
        f"(matrix={counts.shape}, cells={len(obs_names)}, genes={len(var)})"
    )

obs = pd.DataFrame(index=obs_names)
obs.index.name = None
var.index.name = None

has_duplicated_vars = var.index.has_duplicates
with warnings.catch_warnings():
    if has_duplicated_vars:
        warnings.filterwarnings(
            "ignore",
            message="Variable names are not unique.*",
            category=UserWarning,
        )
    adata = ad.AnnData(X=counts, obs=obs, var=var)
adata.obs.index.name = None
adata.var.index.name = None

if has_duplicated_vars:
    std.print_info("merging duplicated gene symbols")
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Variable names are not unique.*",
            category=UserWarning,
        )
        merged_adata = bt.sct.pp.var_names_merge_duplicates(
            adata,
            var_names_column="symbol",
        )
    if merged_adata is not None:
        adata = merged_adata

adata.obs.index.name = None
adata.var.index.name = None
adata.var_names_make_unique()
adata = adata[sorted(adata.obs.index), sorted(adata.var.index)].to_memory()
adata.obs.index.name = None
adata.var.index.name = None
adata.layers["counts"] = adata.X.copy()
adata.uns["scbolt"] = {
    "input_source": "GEO",
    "gsm": args.gsm,
    "matrix_type": "public_count_matrix",
}

if adata.n_obs == 0:
    raise ValueError("imported AnnData has no cells")
if adata.n_vars == 0:
    raise ValueError("imported AnnData has no genes")

args.outfile.parent.mkdir(parents=True, exist_ok=True)
std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
adata.write_h5ad(args.outfile)
