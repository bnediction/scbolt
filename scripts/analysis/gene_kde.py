#!/usr/bin/env python

import os
import argparse
import std
from pathlib import Path

import anndata as ad
from bonesistools import anndatatools as sct

import matplotlib.pyplot as plt


script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="gene_kde",
    description="""Compute gene-related kernel density estimates from single-cell sequencing data.""",
    usage=f"python {script_name} <FILE ...> -o <PATH> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    dest="infiles",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="input file(s) storing counts (format: h5ad)",
)

parser.add_argument(
    "-o",
    "--outpath",
    dest="outpath",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="output directory storing KDE plots",
)

parser.add_argument(
    "--genes",
    dest="genes",
    type=str,
    required=True,
    nargs="+",
    metavar="LITERAL",
    help="gene names for which KDE plots are generated",
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
    "--obs",
    dest="obs",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="plot KDE for each distinct group in adata.obs (default: None)",
)

args = parser.parse_args()

if not args.outpath.exists():
    os.makedirs(args.outpath)

std.print_task(
    f"loading AnnData objects (files={', '.join(std.format_path(file) for file in args.infiles)})"
)
adatas = [ad.read_h5ad(infile) for infile in args.infiles]

for i in range(len(adatas)):
    adatas[i].var_names_make_unique()

if len(args.infiles) > 1:
    std.print_info("concatenating datasets")
    try:
        adata = ad.concat(adatas, axis=0, merge="first", uns_merge="same")
        adata.obs_names_make_unique()  ### handle issue when there are identical barcodes between anndata.
    except Exception as error:
        raise RuntimeError("Anndatas concatenation did not work, aborting") from error
else:
    adata = adatas[0]

del adatas

std.print_task(f"plotting gene KDEs (directory={os.path.relpath(args.outpath)})")
for gene in args.genes:
    if gene not in adata.var.index:
        std.print_warning(f"gene not found: {gene}")
    else:
        fig, ax = sct.pl.kde_plot(adata, gene, layer=args.layer, obs=args.obs)
        plt.savefig(Path(f"{args.outpath}/{gene}.pdf"))
        plt.close()
