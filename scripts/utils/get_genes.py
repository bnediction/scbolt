#!/usr/bin/env python

import os
import std
import argparse
from pathlib import Path

from bonesistools.databases.ncbi import GeneSynonyms

import scanpy as sc

import warnings

warnings.filterwarnings("ignore")

parser = argparse.ArgumentParser(
    prog="get_genes",
    description="""Retrieve gene names.""",
    usage="""python get_genes.py [-h] <FILE> <FILE> [--axis <obs | var>] [--standardization]""",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing AnnData object (format: h5ad or loom)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing gene names (format: txt)",
)

parser.add_argument(
    "--axis",
    dest="axis",
    choices=["obs", "var"],
    default="var",
    required=False,
    metavar="[obs | var]",
    help="axis corresponding to genes (default: var)",
)

parser.add_argument(
    "--standardization",
    dest="standardization",
    required=False,
    action="store_true",
    help="standardize gene names with their NCBI reference names",
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(os.path.dirname(args.outfile))

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")
if str(args.infile).endswith(".h5ad"):
    adata = sc.read_h5ad(args.infile)
elif str(args.infile).endswith(".loom"):
    adata = sc.read_loom(args.infile)
else:
    raise IOError("incorrect format (h5ad or loom format expected)")

if args.axis == "obs":
    gene_list = list(adata.obs.index)
else:
    gene_list = list(adata.var.index)

if args.standardization:
    std.print_info("standardizing gene names")
    gene_list = GeneSynonyms()(gene_list)

std.print_task(f"saving gene list (file={std.format_path(args.outfile)})")
with open(args.outfile, "w") as file:
    for gene in gene_list:
        file.write(f"{gene}\n")
