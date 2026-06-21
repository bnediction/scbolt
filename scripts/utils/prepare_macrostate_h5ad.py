#!/usr/bin/env python

from pathlib import Path
from typing import Any

import argparse
import cli
import std

import anndata as ad


def require_key(collection: Any, key: str, group: str) -> None:
    if key not in collection:
        raise KeyError(f"missing AnnData field: {group}['{key}']")


script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="prepare_macrostate_h5ad",
    description="Prepare a precomputed macrostate AnnData file for binarization.",
    usage=f"python {script_name} <FILE> <FILE> --representation <LITERAL> [<args>]",
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input macrostate-annotated AnnData file (format: h5ad)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output prepared AnnData file (format: h5ad)",
)

parser.add_argument(
    "--macrostate-obs",
    dest="macrostate_obs",
    type=str,
    required=False,
    default="macrostate",
    metavar="LITERAL",
    help="obs column storing macrostates (default: macrostate)",
)

parser.add_argument(
    "--condition-obs",
    dest="condition_obs",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="obs column storing experimental conditions (default: None)",
)

parser.add_argument(
    "--condition",
    dest="condition",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="condition assigned to all cells (default: None)",
)

parser.add_argument(
    "--prefix-macrostates",
    dest="prefix_macrostates",
    action="store_true",
    help="prefix macrostates with condition labels",
)

parser.add_argument(
    "--representation",
    dest="representation",
    type=str,
    required=True,
    metavar="LITERAL",
    help="Embedding representation required in adata.obsm.",
)

args = parser.parse_args()

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")
adata = ad.read_h5ad(args.infile)

std.print_task("validating macrostate AnnData metadata")
require_key(adata.layers, "log-norm", "layers")
require_key(adata.obs, args.macrostate_obs, "obs")
require_key(adata.obsm, args.representation, "obsm")

if args.condition is not None:
    if args.condition_obs is None:
        args.condition_obs = "condition"
    std.print_task(
        f"assigning condition (condition={args.condition}, obs={args.condition_obs})"
    )
    adata.obs[args.condition_obs] = args.condition

if args.prefix_macrostates:
    if args.condition_obs is None:
        raise ValueError(
            "--condition-obs is required when --prefix-macrostates is used"
        )
    require_key(adata.obs, args.condition_obs, "obs")
    std.print_task(
        "prefixing macrostates "
        f"(condition={args.condition_obs}, obs={args.macrostate_obs})"
    )
    adata.obs[args.macrostate_obs] = (
        adata.obs[args.condition_obs].astype(str)
        + "_"
        + adata.obs[args.macrostate_obs].astype(str)
    ).astype("category")

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
args.outfile.parent.mkdir(parents=True, exist_ok=True)
std.write_h5ad(adata, filename=args.outfile, compression="gzip")
