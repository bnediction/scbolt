#!/usr/bin/env python

import argparse
import cli
import tempfile
import warnings
from pathlib import Path

import bonesistools as bt
import pandas as pd

import std

script_name = Path(__file__).name


parser = argparse.ArgumentParser(
    formatter_class=cli.HelpFormatter,
    prog="load_geo",
    description="Download and import a GEO count matrix into AnnData.",
    usage=(f"python {script_name} <GSM> <FILE> [--cache-dir <DIR>]"),
)

parser.add_argument("gsm", metavar="GSM")
parser.add_argument("outfile", type=lambda x: Path(x).resolve(), metavar="FILE")
parser.add_argument("--cache-dir", type=lambda x: Path(x).resolve(), metavar="DIR")
parser.add_argument("--quiet", action="store_true")

args = parser.parse_args()

std.print_task(f"loading GEO count matrix (sample={args.gsm})")
if args.cache_dir is None:
    with tempfile.TemporaryDirectory(prefix="scbolt-geo-") as cache_dir:
        adata = bt.sct.datasets.from_geo(
            args.gsm,
            cache_dir=cache_dir,
            quiet=args.quiet,
        )
else:
    adata = bt.sct.datasets.from_geo(
        args.gsm,
        cache_dir=args.cache_dir,
        quiet=args.quiet,
    )

if "symbol" in adata.var:
    symbols = pd.Index(adata.var["symbol"].astype(str), name=None)
    if symbols.has_duplicates:
        std.print_info("merging duplicated gene symbols")
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Variable names are not unique.*",
                category=UserWarning,
            )
            adata.var_names = symbols
            bt.sct.pp.merge_duplicate_vars(adata, copy=False)

keep_var_columns = [column for column in ["Accession", "symbol"] if column in adata.var]
adata.var = adata.var.loc[:, keep_var_columns].copy()
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
std.write_h5ad(adata, filename=args.outfile)
