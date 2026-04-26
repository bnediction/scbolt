#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse, cli
from pathlib import Path

import math
import numpy as np

import rdata
import pandas as pd
import anndata as ad
import scanpy as sc
import bonesistools as bt
from pypairs import pairs

import matplotlib.pyplot as plt

bt.sct.pl.set_default_params()

pd.DataFrame.iteritems = pd.DataFrame.items

def marker_pairs_converter(ensembl_id_marker_pairs, output_identifier_type: str="official_name"):
    """Convert marker pairs from ensembl_id into their corresponding aliases."""
    genesyn = bt.dbs.ncbi.GeneSynonyms()
    converted_marker_pairs = dict()
    for cc, pairs in ensembl_id_marker_pairs.items():
        cycle_pairs = list()
        for _, (first, second) in pairs.iterrows():
            first_alias = genesyn.conversion(first, "ensembl_id", output_identifier_type)
            second_alias = genesyn.conversion(second, "ensembl_id", output_identifier_type)
            cycle_pairs.append([
                first_alias if first_alias is not None else first,
                second_alias if second_alias is not None else second
            ])
        converted_marker_pairs[cc] = cycle_pairs
    return converted_marker_pairs

def median_absolute_deviation(x, consistency=False):
    """Compute the mean absolute deviation (MAD).
    If consistency is true, adjust by a factor for asymptotically normal consistency.
    Asymptotic normal consistency means that:
        E[MAD(X_1,...,X_n)] = sigma
    for X_i following a gaussian distribution N(mu, sigma^2).
    """
    constant = 1.4826 if consistency else 1
    return constant*np.median(np.absolute(x - np.median(x)))

parser = argparse.ArgumentParser(
    prog="filtering",
    description=
    """
    Calculate metrics (proportions of genes encoding mitocondrial and ribosomal proteins, \
    quality control metrics), assign cell to a cell cycle phase \
    and filter low-quality genes and cells.
    """,
    usage="python filtering.py <FILE> <FILE> [--marker <FILE>] [<args>]"
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)"
)

parser.add_argument(
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing counts before filtering (format: h5ad)"
)

parser.add_argument(
    "--marker",
    dest="marker_infile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="input file storing cell cycle phase markers (rds format)"
)

parser.add_argument(
    "--gene-dropout",
    dest="gene_dropout",
    action=cli.Range,
    type=float,
    min=0,
    max=1,
    required=False,
    default=1,
    help="maximum percentage of cell dropout required for a gene to pass filtering (default: 1)"
)

parser.add_argument(
    "--gene-expression",
    dest="gene_expression",
    action=cli.Min_and_max,
    type=int,
    min=0,
    max=math.inf,
    required=False,
    default=[0, math.inf],
    help="minimum and maximum number of expressed cells required for a gene to pass filtering (default: [0, inf])"
)

parser.add_argument(
    "--gene-counts",
    dest="gene_counts",
    action=cli.Min_and_max,
    type=int,
    min=0,
    max=math.inf,
    required=False,
    default=[0, math.inf],
    help="minimum and maximum number of counts required for a gene to pass filtering (default: [0, inf])"
)

parser.add_argument(
    "--cell-dropout",
    dest="cell_dropout",
    action=cli.Range,
    type=float,
    min=0,
    max=1,
    required=False,
    default=1,
    help="maximum percentage of gene dropout required for a cell to pass filtering (default: 1)"
)

parser.add_argument(
    "--cell-expression",
    dest="cell_expression",
    action=cli.Min_and_max,
    type=int,
    min=0,
    max=math.inf,
    required=False,
    default=[0, math.inf],
    help="minimum and maximum number of expressed genes required for a cell to pass filtering (default: [0, inf])"
)

parser.add_argument(
    "--cell-reads",
    dest="cell_reads",
    action=cli.Min_and_max,
    type=int,
    min=0,
    max=math.inf,
    required=False,
    default=[0, math.inf],
    help="minimum and maximum number of reads required for a cell to pass filtering (default: [0, inf])"
)

parser.add_argument(
    "--mad-deviation",
    dest="mad_deviation",
    type=float,
    nargs=2,
    required=False,
    default=[math.inf,math.inf],
    metavar="FLOAT",
    help="factor droping cells for which their total reads are smaller or higher than this factor*mean-absolute-deviation with respect to the median (default: [inf,inf])"
)

parser.add_argument(
    "--consistent-mad",
    dest="consistent_mad",
    action="store_true",
    required=False,
    help="use normalized mean absolute deviation"
)

parser.add_argument(
    "--mt",
    dest="mt",
    action=cli.Range,
    type=float,
    min=0,
    max=1,
    required=False,
    default=1,
    help="maximum proportion of expressed genes encoding mithocondrion proteins required for a cell to pass filtering (default: 1)"
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    type=int,
    required=False,
    default=2000,
    help="number of highly variable genes (default: 2000)"
)

parser.add_argument(
    "--filter-non-hvg",
    dest="filter_non_hvg",
    action="store_true",
    required=False,
    help="filter non-highly variable genes"
)

args = parser.parse_args()

if any(v<0 for v in args.mad_deviation):
    raise argparse.ArgumentError(f"expected positive values, but received {args.mad_deviation}")

outpath = Path(os.path.dirname(args.outfile))
if not outpath.exists():
    os.makedirs(outpath)

std.print_task(f"loading file {str(args.infile)}")

adata = ad.read_h5ad(Path(f"{args.infile}").resolve())

std.print_task(f"initializing settings")

adata.layers["counts"] = adata.X.copy()
adata.var_names_make_unique()

shape = {"init":adata.shape}

std.print_task("classifying genes encoding mitocondrial proteins")
bt.sct.tl.mitochondrial_genes(
    adata,
    index_type="name",
    key="mt",
    axis=1,
    copy=False
)

std.print_task("classifying genes encoding ribosomal proteins")
bt.sct.tl.ribosomal_genes(
    adata,
    index_type="name",
    key="rps",
    axis=1,
    copy=False
)

if args.marker_infile is None:
    std.print_warning("cannot classify cell cycle phases: marker file not specified")
else:
    std.print_task(f"classifying cell cycle phases (using file {str(args.marker_infile)})")
    std.print_debug("parsing R file")
    parser = rdata.parser.parse_file(args.marker_infile)
    std.print_debug("converting R-readable parser into Python-readable parser")
    marker_pairs = rdata.conversion.convert(parser)
    std.print_info("scoring cell cycle phases for each cell")
    marker_pairs = marker_pairs_converter(marker_pairs, "official_name")
    scores = pairs.cyclone(adata, marker_pairs)
    adata.obs.rename(columns={"pypairs_G1": "G1_score", "pypairs_S": "S_score", "pypairs_G2M": "G2M_score"}, inplace=True)

std.print_task("calculating quality control metrics")
sc.pp.calculate_qc_metrics(
    adata,
    qc_vars=["mt","rps"],
    percent_top=None,
    log1p=False,
    inplace=True,
)

std.print_info("plotting violin plots before filtering")
ax = sc.pl.violin(
    adata=adata,
    keys=["n_genes_by_counts", "total_counts", "pct_counts_mt", "pct_counts_rps"],
    jitter=0.4,
    multi_panel=True,
    stripplot=False,
    show=False,
    save=False
)
for i, title in zip(range(4), [r"gene number", r"gene counts", r"mitochondrion proportion", r"ribosome proportion"]):
    ax.axes[0,i].set_title(title)
plt.savefig(f"{outpath}/raw-data.pdf")
plt.close()

std.print_task(f"preprocessing counting data")

mad = median_absolute_deviation(np.log(adata.obs.total_counts),consistency=(args.consistent_mad))
reads = [
    np.exp(np.median(np.log(adata.obs.total_counts)) - args.mad_deviation[0]*mad),
    np.exp(np.median(np.log(adata.obs.total_counts)) + args.mad_deviation[1]*mad)
]

ylim = [0, round(math.ceil(max(adata.obs.total_counts)+1000),-3)]
fig, ax = plt.subplots(nrows=1, ncols=2)
sc.pl.violin(
    adata=adata,
    keys="total_counts",
    stripplot=False,
    jitter=0.4,
    ax=ax[0],
    show=False,
    save=False
)
ax[0].axhline(reads[0], linewidth=1.5, linestyle='--', color=bt.sct.pl.get_color("red"))
ax[0].axhline(reads[1], linewidth=1.5, linestyle='--', color=bt.sct.pl.get_color("red"))
ax[0].set_ylim(ylim)
ax[0].set(title="raw")

std.print_info(f"filtering low-quality genes")

bt.sct.pp.filter_var(
    adata,
    "pct_dropout_by_counts",
    lambda x: (x <= 1e2*args.gene_dropout)
)

bt.sct.pp.filter_var(
    adata,
    "n_cells_by_counts",
    lambda x: (x >= args.gene_expression[0]) & (x < args.gene_expression[1])
)

bt.sct.pp.filter_var(
    adata,
    "total_counts",
    lambda x: (x >= args.gene_counts[0]) & (x < args.gene_counts[1])
)

std.print_info(f"filtering low-quality cells")

bt.sct.pp.filter_obs(
    adata,
    "n_genes_by_counts",
    lambda x: (x >= (1-args.cell_dropout)*adata.n_vars)
)

bt.sct.pp.filter_obs(
    adata,
    "n_genes_by_counts",
    lambda x: (x >= args.cell_expression[0]) & (x < args.cell_expression[1])
)

bt.sct.pp.filter_obs(
    adata,
    "total_counts",
    lambda x: (x >= args.cell_reads[0]) & (x < args.cell_reads[1])
)

bt.sct.pp.filter_obs(
    adata,
    "total_counts",
    lambda x: (x >= reads[0]) & (x < reads[1])
)

bt.sct.pp.filter_obs(
    adata,
    "pct_counts_mt",
    lambda x: x < 1e2*args.mt
)

std.print_task(f"computing top {args.hvg} highly variable genes")

sc.pp.highly_variable_genes(
    adata,
    layer="counts",
    flavor="seurat_v3",
    span=0.3,
    n_bins=20,
    n_top_genes=args.hvg,
    inplace=True
)
if args.filter_non_hvg:
    std.print_info(f"filtering non-highly variable genes")
    adata._inplace_subset_var(adata.var.highly_variable)
else:
    std.print_info(f"keeping non-highly variable genes")

shape["final"] = adata.shape

std.print_task("plotting violin plots and bar charts")

sc.pl.violin(
    adata=adata,
    keys="total_counts",
    jitter=0.4,
    multi_panel=None,
    stripplot=False,
    ax=ax[1],
    show=False,
    save=False,
)
ax[1].axhline(reads[0], linewidth=1.5, linestyle='--', color=bt.sct.pl.get_color("red"))
ax[1].axhline(reads[1], linewidth=1.5, linestyle='--', color=bt.sct.pl.get_color("red"))
ax[1].set_ylim(ylim)
ax[1].set(title="filtered")
plt.savefig(f"{outpath}/total-counts.pdf")

ax = sc.pl.violin(
    adata=adata,
    keys=["n_genes_by_counts", "total_counts", "pct_counts_mt", "pct_counts_rps"],
    jitter=0.4,
    multi_panel=True,
    stripplot=False,
    show=False,
    save=False
)
for i, title in zip(range(4), [r"gene number", r"gene counts", r"mitochondrion proportion", r"ribosome proportion"]):
    ax.axes[0,i].set_title(title)
plt.savefig(f"{outpath}/filtered-data.pdf")

if args.marker_infile:
    fig, ax = plt.subplots(nrows=1, ncols=1)
    ax = adata.obs.pypairs_cc_prediction.value_counts().plot.bar(rot=0)
    ax.set(xlabel="cell cycle phases")
    plt.savefig(f"{outpath}/cell-cycles-counting.pdf")

std.print_task(f"saving data in {str(args.outfile)}")
adata.write_h5ad(
    filename=args.outfile,
    compression="gzip"
)

std.print_result(f"gene number: [before filtering: {shape['init'][0]}, after filtering: {shape['final'][0]}, removed: {shape['init'][0] - shape['final'][0]}]")
std.print_result(f"cell number: [before filtering: {shape['init'][1]}, after filtering: {shape['final'][1]}, removed: {shape['init'][1] - shape['final'][1]}]")
