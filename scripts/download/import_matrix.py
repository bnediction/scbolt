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


def make_index(values: pd.Series, *, unique: bool = False) -> pd.Index:
    index = pd.Index(values.astype(str).to_numpy(), name=None)
    if unique:
        return ad_utils.make_index_unique(index)
    return index


def make_var(features: pd.DataFrame) -> pd.DataFrame:
    var = pd.DataFrame(
        index=make_index(
            features.iloc[:, 1] if features.shape[1] > 1 else features.iloc[:, 0],
            unique=True,
        )
    )
    var["gene_id"] = features.iloc[:, 0].astype(str).to_numpy()
    if features.shape[1] > 1:
        var["gene_name"] = features.iloc[:, 1].astype(str).to_numpy()
    if features.shape[1] > 2:
        var["feature_type"] = features.iloc[:, 2].astype(str).to_numpy()
    return var


def import_matrix(
    matrix: Path,
    barcodes: Path,
    features: Path,
    condition: str,
    gsm: str | None,
) -> ad.AnnData:
    std.print_info(f"loading MatrixMarket counts (file={std.format_path(matrix)})")
    counts = scipy.io.mmread(matrix).tocsr()

    std.print_info(f"loading barcodes (file={std.format_path(barcodes)})")
    obs_names = make_index(read_table(barcodes).iloc[:, 0], unique=True)

    std.print_info(f"loading feature annotations (file={std.format_path(features)})")
    var = make_var(read_table(features))

    if counts.shape == (len(var), len(obs_names)):
        counts = counts.T.tocsr()
    elif counts.shape != (len(obs_names), len(var)):
        raise ValueError(
            "matrix shape is incompatible with barcodes and genes "
            f"(matrix={counts.shape}, cells={len(obs_names)}, genes={len(var)})"
        )

    obs = pd.DataFrame(index=obs_names)
    obs["condition"] = condition

    adata = ad.AnnData(X=counts, obs=obs, var=var)
    adata.layers["counts"] = adata.X.copy()
    adata.uns["scbolt"] = {
        "input_source": "GEO",
        "gsm": gsm,
        "matrix_type": "public_count_matrix",
    }
    return adata


parser = argparse.ArgumentParser(
    prog="import_matrix",
    description="Import a public 10x-style count matrix into AnnData.",
    usage=(
        f"python {script_name} <FILE> <FILE> <FILE> <FILE> "
        "--condition <CONDITION> [--gsm <GSM>]"
    ),
)

parser.add_argument("matrix", type=lambda x: Path(x).resolve(), metavar="FILE")
parser.add_argument("barcodes", type=lambda x: Path(x).resolve(), metavar="FILE")
parser.add_argument("features", type=lambda x: Path(x).resolve(), metavar="FILE")
parser.add_argument("outfile", type=lambda x: Path(x).resolve(), metavar="FILE")
parser.add_argument("--condition", required=True, metavar="CONDITION")
parser.add_argument("--gsm", default=None, metavar="GSM")

args = parser.parse_args()

adata = import_matrix(
    matrix=args.matrix,
    barcodes=args.barcodes,
    features=args.features,
    condition=args.condition,
    gsm=args.gsm,
)

if adata.n_obs == 0:
    raise ValueError("imported AnnData has no cells")
if adata.n_vars == 0:
    raise ValueError("imported AnnData has no genes")

args.outfile.parent.mkdir(parents=True, exist_ok=True)
std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
adata.write_h5ad(args.outfile)
