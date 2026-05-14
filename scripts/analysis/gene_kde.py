#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path

import anndata as ad
from bonesistools import anndatatools as sct

import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(
    prog="Single-cell gene kde",
    description="""Compute gene-related kernel density distribution from single-cell sequencing data.""",
    usage="python gene_kde.py <FILE...> -o <PATH> [<args>]",
)

parser.add_argument(
    dest="infiles",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="input file(s) (h5ad format)",
)

parser.add_argument(
    "-o",
    "--outpath",
    dest="outpath",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="output path",
)

parser.add_argument(
    "--genes",
    dest="genes",
    type=str,
    required=True,
    nargs="+",
    metavar="LITERAL",
    help="genes of interest",
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
    help="plot kde for each distinct group in adata.obs (default: None)",
)

args = parser.parse_args()

if not args.outpath.exists():
    os.makedirs(args.outpath)

adatas = [ad.read_h5ad(infile) for infile in args.infiles]

for i in range(len(adatas)):
    adatas[i].var_names_make_unique()

if len(args.infiles) > 1:
    try:
        adata = ad.concat(adatas, axis=0, merge="first", uns_merge="same")
        adata.obs_names_make_unique()  ### handle issue when there are identical barcodes between anndata.
    except:
        raise RuntimeError("Anndatas concatenation did not work, aborting")
else:
    adata = adatas[0]

del adatas

for gene in args.genes:
    if gene not in adata.var.index:
        print(f"gene {gene} not found.")
    else:
        fig, ax = sct.pl.kde_plot(adata, gene, layer=args.layer, obs=args.obs)
        plt.savefig(Path(f"{args.outpath}/{gene}.pdf"))
        plt.close()
