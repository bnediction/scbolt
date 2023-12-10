#!/usr/bin/python3

from pathlib import Path
import os

import numpy as np, random

import pandas as pd
import scanpy as sc
import rdata
from pypairs import pairs

import matplotlib.pyplot as plt, py_src.plot_settings, py_src.color_settings as color
from matplotlib.ticker import FormatStrFormatter

random.seed(1000)

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

data_outpath = Path(f"{args['outpath']}/tables")
fig_outpath = Path(f"{args['outpath']}/figures")

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

adata = sc.read_h5ad(Path(f"{args['infile']}").resolve())

ensembl_to_symbol = dict()
for _, row in adata.var.iterrows():
    ensembl_to_symbol[row["gene_ids"]] = row["symbol"]

parser = rdata.parser.parse_file(args["cycle_phases_file"])
marker_pairs = rdata.conversion.convert(parser)
marker_pairs = marker_pairs_converter(ensembl_to_symbol, marker_pairs)
scores = pairs.cyclone(adata, marker_pairs)

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.scatter(adata.obs.pypairs_G1, adata.obs.pypairs_G2M, s=30, facecolors=color.white, edgecolors=color.blue, alpha=1)
ax.set_xlabel(r"score $\mathrm{G_{1}}$")
ax.set_ylabel(r"score $\mathrm{G_{2}/M}$")
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
plt.savefig(f"{fig_outpath}/cell-cycle-phases-assignment")

adata.var_names_make_unique()

adata.var["mitochondrion"] = adata.var_names.str.startswith("mt-")          # annotate the group of mitochondrial genes
adata.var["ribosome"] = adata.var_names.str.startswith(("Rps","Rpl","Mrp")) # annotate the group of ribosomal genes

sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True, qc_vars=["mitochondrion","ribosome"])
adata.obs.rename(columns={"total_counts": "counts_by_barcode"}, inplace=True)
adata.var.rename(columns={"total_counts": "counts_by_gene"}, inplace=True)
ax = sc.pl.violin(
    adata=adata,
    keys=["n_genes_by_counts", "counts_by_barcode", "pct_counts_mitochondrion", "pct_counts_ribosome"],
    jitter=0.4,
    multi_panel=True,
    stripplot=False,
    show=False,
    save=False
)
ax.axes[0,0].set_title(r"gene number")
ax.axes[0,1].set_title(r"gene counts")
ax.axes[0,2].set_title(r"mitochondrion proportion")
ax.axes[0,3].set_title(r"ribosome proportion")
plt.savefig(f"{fig_outpath}/violin-plot-before-filtering.png")
