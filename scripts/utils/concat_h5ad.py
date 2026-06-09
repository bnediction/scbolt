#!/usr/bin/env python

from pathlib import Path

import argparse
import std

import anndata as ad

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="concat_h5ad",
    description="Concatenate AnnData files along observations.",
    usage=f"python {script_name} <FILE...> --outfile <FILE>",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "infiles",
    type=lambda x: Path(x).resolve(),
    nargs="+",
    metavar="FILE",
    help="input AnnData files (format: h5ad)",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output concatenated AnnData file (format: h5ad)",
)

args = parser.parse_args()

adatas = []
for infile in args.infiles:
    std.print_task(f"loading AnnData (file={std.format_path(infile)})")
    adatas.append(ad.read_h5ad(infile))

std.print_task(f"concatenating AnnData objects (files={len(adatas)})")
try:
    adata = ad.concat(
        adatas=adatas,
        axis=0,
        join="inner",
        merge="first",
        uns_merge="same",
        index_unique="-",
    )
except Exception as error:
    raise RuntimeError("AnnData concatenation failed") from error

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
args.outfile.parent.mkdir(parents=True, exist_ok=True)
adata.write_h5ad(filename=args.outfile, compression="gzip")
