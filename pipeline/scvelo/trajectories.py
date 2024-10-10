#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path

import re

import pandas as pd
import anndatatools as adt, scvelo as scv

import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(
    prog="scvelo of sc-RNAseq data",
    description="""From one-condition sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    perform scvelo analysis.""",
    usage="python scvelo.py <FILE> <PATH> [<args>]"
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="file in h5ad format"
)

parser.add_argument(
    "outpath",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=False,
    metavar="LITERAL",
    help="column name such as adata.obs[`LITERAL`] distinguishes cluster"
)


s = """data/rna/ctrl/cluster/tables/counts_labels.h5ad data/rna/ctrl/scvelo --cluster leiden"""

args = parser.parse_args(s.split())

if not args.outpath.exists():
    os.makedirs(args.outpath)

print(f"Loading data...")

adata = scv.read(args.infile, cache=True)
adata2 = scv.datasets.pancreas()

scv.set_figure_params()
adt.pl.set_default()

scv.pl.proportions(
    adata,
    groupby=args.cluster,
    fontsize=plt.rcParams["font.size"],
    figsize=(9,5),
    show=False,
)
plt.savefig(Path(f"{args.outpath}/proportions.pdf"))
plt.close()

print("Computing metrics...")

# scv.pp.remove_duplicate_cells(adata)
# scv.pp.filter_and_normalize(adata, min_shared_counts=20, n_top_genes=2000)
adata.X = adata.layers["raw"]
scv.pp.moments(adata, n_pcs=30, n_neighbors=30)

print("Plotting trajectories...")

scv.tl.velocity(adata)
scv.tl.velocity_graph(adata)

scv.pl.velocity_embedding_stream(adata, basis='umap')
