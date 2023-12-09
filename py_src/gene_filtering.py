#!/usr/bin/python3

from pathlib import Path

import os
import rdata
import numpy as np
import scanpy as sc
import pandas as pd
from pypairs import pairs
import init_colours

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter

pd.DataFrame.iteritems = pd.DataFrame.items

def median_absolute_deviation(x):
    return np.median(np.absolute(x - np.median(x)))

def marker_pairs_converter(ensembl_to_symbol: dict, ensembl_marker_pairs):
    """convert marker pairs from ensembl id into symbol id"""

    symbol_marker_pairs = dict()
    for cycle, pairs in ensembl_marker_pairs.items():
        cycle_pairs = list()
        for _, (first, second) in pairs.iterrows():
            if first in ensembl_to_symbol.keys() and second in ensembl_to_symbol.keys():
                cycle_pairs.append([ensembl_to_symbol[first], ensembl_to_symbol[second]])
        symbol_marker_pairs[cycle] = cycle_pairs
    return symbol_marker_pairs

args={
    "infile":Path("data/scRNA/raw/ct/ct.h5ad").resolve(),
    "cycle_phases_file":Path("data/public/cycle-phases/mouse_cycle_markers.rds").resolve(),
    "outpath":Path("data/scRNA/gene_filtering/ct").resolve(),
    "mitochondrial_threshold":0.1,
    "upper_mad":2,
    "lower_mad":3
}

outpath_data = Path(f"{args['outpath']}/tables")
outpath_fig = Path(f"{args['outpath']}/figures")

if not outpath_data.exists():
    os.makedirs(outpath_data)
if not outpath_fig.exists():
    os.makedirs(outpath_fig)

adata = sc.read_h5ad(Path(f"{args['infile']}").resolve())

ensembl_to_symbol = dict()
for _, row in adata.var.iterrows():
    ensembl_to_symbol[row["gene_ids"]] = row["symbol"]

parser = rdata.parser.parse_file(args["cycle_phases_file"])
marker_pairs = rdata.conversion.convert(parser)
marker_pairs = marker_pairs_converter(ensembl_to_symbol, marker_pairs)
scores = pairs.cyclone(adata, marker_pairs)

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.scatter(adata.obs.pypairs_G1, adata.obs.pypairs_G2M, s=30, facecolors=colour_white, edgecolors=colour_blue, alpha=1)
ax.set_xlim([0, 1]); ax.set_ylim([0, 1])
ax.set_xlabel(r'$\mathrm{G_{1}}$ score', fontsize=13)
ax.set_ylabel(r'$\mathrm{G_{2}/M}$ score', fontsize=13)
plt.sca(ax)
plt.xticks(fontsize=11)
plt.yticks(fontsize=11)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.savefig(f"{outpath_fig}/cell cycle phases assignment")
