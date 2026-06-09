#!/usr/bin/env python

import argparse
import gzip
from pathlib import Path

import anndata as ad
from anndata import utils as ad_utils
import pandas as pd
import scipy.io

import std

script_name = Path(__file__).name


def read_table(path: Path) -> pd.DataFrame:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as handle:
        return pd.read_csv(handle, sep="\t", header=None, dtype=str)


def make_var(features: pd.DataFrame) -> pd.DataFrame:
    var_names = pd.Index(
        (
            features.iloc[:, 1]
            if features.shape[1] > 1
            else features.iloc[:, 0]
        ).astype(str),
        name=None,
    )
    var_names = ad_utils.make_index_unique(var_names)
    var = pd.DataFrame(
        index=var_names,
    )
    var["gene_id"] = features.iloc[:, 0].astype(str).to_numpy()
    if features.shape[1] > 1:
        var["gene_name"] = features.iloc[:, 1].astype(str).to_numpy()
    if features.shape[1] > 2:
        var["feature_type"] = features.iloc[:, 2].astype(str).to_numpy()
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

std.print_info(f"loading MatrixMarket counts (file={std.format_path(args.matrix)})")
counts = scipy.io.mmread(args.matrix).tocsr()

std.print_info(f"loading barcodes (file={std.format_path(args.barcodes)})")
obs_names = pd.Index(
    read_table(args.barcodes).iloc[:, 0].astype(str),
    name=None,
)
obs_names = ad_utils.make_index_unique(obs_names)

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

adata = ad.AnnData(X=counts, obs=obs, var=var)

accession = adata.var["gene_id"] if "gene_id" in adata.var else adata.var.index
symbol = adata.var["symbol"] if "symbol" in adata.var else adata.var.index
adata.var = pd.DataFrame(
    {
        "Accession": pd.Series(accession, index=adata.var.index).astype(str),
        "symbol": pd.Series(symbol, index=adata.var.index).astype(str),
    },
    index=adata.var.index,
)
adata = adata[sorted(adata.obs.index), sorted(adata.var.index)].to_memory()
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
