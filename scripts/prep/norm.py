#!/usr/bin/env python

import os
import std
import argparse
from pathlib import Path

import anndata as ad
import scanpy as sc
import numpy as np
import bonesistools as bt

import warnings

warnings.filterwarnings("ignore")
script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="norm",
    description=(
        "Normalize counts with different operations: standardization w.r.t. "
        "library size, log-transformation, scaling and correction of unwanted effects."
    ),
    usage=f"python {script_name} <FILE> <FILE> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing normalized counts (format: h5ad)",
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used (if not specified, use adata.X)",
)

parser.add_argument(
    "--correction",
    dest="correction",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="unwanted effects to correct (default: None)",
)

parser.add_argument(
    "--jobs",
    dest="jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of allocated processors (default: 1)",
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")

adata = ad.read_h5ad(args.infile)

if args.layer:
    adata.X = adata.layers[args.layer].copy()

std.print_task("normalizing read counts")

std.print_info("standardizing counts by library size (layer=norm)")
adata.layers["norm"] = adata.X.copy()
sc.pp.normalize_total(adata, target_sum=1e4, layer="norm", copy=False)

std.print_info("performing log-transformation (layer=log-norm)")
adata.layers["log-norm"] = adata.layers["norm"].copy()
sc.pp.log1p(adata, base=np.exp(1), layer="log-norm", copy=False)

std.print_info("scaling to unit variance and zero mean (layer=scale)")
adata.layers["scale"] = adata.layers["log-norm"].copy()
sc.pp.scale(adata, layer="scale", copy=False)

if args.correction:
    std.print_info("correcting unwanted effects (layer: correct)")
    adata.layers["correct"] = adata.layers["log-norm"].copy()
    bt.sct.pp.regress_out(
        adata,
        keys=args.correction,
        layer="correct",
        intercept=False,
        copy=False,
        n_jobs=args.jobs,
    )
    sc.pp.scale(adata, layer="correct", copy=False)
else:
    std.print_info("no unwanted effects specified")
    adata.layers["correct"] = adata.layers["scale"].copy()

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
adata.write_h5ad(filename=args.outfile, compression="gzip")
