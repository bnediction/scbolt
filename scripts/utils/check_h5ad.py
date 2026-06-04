#!/usr/bin/env python

import sys
from pathlib import Path

import argparse
import h5py
import std

parser = argparse.ArgumentParser(
    prog="check_h5ad",
    description="Check that an AnnData H5AD file contains required metadata keys.",
    usage=(
        "python check_h5ad.py <FILE...> [--obs <KEY...>] [--var <KEY...>] "
        "[--obsm <KEY...>] [--obsp <KEY...>] [--layers <KEY...>]"
    ),
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "h5ad",
    type=lambda x: Path(x).resolve(),
    nargs="+",
    metavar="FILE",
    help="input AnnData file (format: h5ad)",
)

parser.add_argument(
    "--obs",
    dest="obs",
    nargs="*",
    default=[],
    metavar="KEY",
    help="required keys in adata.obs",
)

parser.add_argument(
    "--var",
    dest="var",
    nargs="*",
    default=[],
    metavar="KEY",
    help="required keys in adata.var",
)

parser.add_argument(
    "--obsm",
    dest="obsm",
    nargs="*",
    default=[],
    metavar="KEY",
    help="required keys in adata.obsm",
)

parser.add_argument(
    "--obsp",
    dest="obsp",
    nargs="*",
    default=[],
    metavar="KEY",
    help="required keys in adata.obsp",
)

parser.add_argument(
    "--layers",
    dest="layers",
    nargs="*",
    default=[],
    metavar="KEY",
    help="required keys in adata.layers",
)

args = parser.parse_args()

if len(args.h5ad) == 1:
    std.print_task(f"checking AnnData metadata (file={std.format_path(args.h5ad[0])})")
else:
    std.print_task(f"checking AnnData metadata (files={len(args.h5ad)})")

missing = []
for path in args.h5ad:
    if not path.is_file():
        missing.append(f"{std.format_path(path)}")
        continue

    try:
        h5ad = h5py.File(path, "r")
    except OSError as error:
        print(
            f"invalid AnnData file: {std.format_path(path)} ({error})", file=sys.stderr
        )
        sys.exit(1)

    with h5ad:
        for group_name, keys in {
            "obs": args.obs,
            "var": args.var,
            "obsm": args.obsm,
            "obsp": args.obsp,
            "layers": args.layers,
        }.items():
            for key in keys:
                if group_name not in h5ad or key not in h5ad[group_name]:
                    missing.append(f"{std.format_path(path)}:{group_name}/{key}")

if missing:
    print(f"missing AnnData keys/files: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

std.print_result("h5ad metadata check passed")
