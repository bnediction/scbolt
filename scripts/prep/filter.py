#!/usr/bin/env python

import os
import std
import argparse
import cli
import warnings
from pathlib import Path

import math
import numpy as np

import rdata
import pandas as pd
import anndata as ad
import bonesistools as bt
import pypairs

import matplotlib.pyplot as plt

std.set_default_plot_params(bt.omics.pl)

setattr(pd.DataFrame, "iteritems", pd.DataFrame.items)
script_name = Path(__file__).name


def marker_pairs_converter(
    ensembl_id_marker_pairs,
    genesyn,
    output_identifier_type: str = "official_name",
):
    """Convert marker pairs from ensembl_id into their corresponding aliases."""
    converted_marker_pairs = dict()
    for cc, pairs in ensembl_id_marker_pairs.items():
        cycle_pairs = list()
        for _, (first, second) in pairs.iterrows():
            first_alias = genesyn.conversion(
                first, "ensembl_id", output_identifier_type
            )
            second_alias = genesyn.conversion(
                second, "ensembl_id", output_identifier_type
            )
            cycle_pairs.append(
                [
                    first_alias if first_alias is not None else first,
                    second_alias if second_alias is not None else second,
                ]
            )
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
    return constant * np.median(np.absolute(x - np.median(x)))


def format_filtering_coverage(name, kept, total):
    removed = total - kept
    pct = 0 if total == 0 else 100 * kept / total
    return f"{name}: kept={kept}/{total} ({pct:.1f}%), removed={removed}"


def format_range(values):
    lower, upper = values
    upper = "inf" if math.isinf(upper) else upper
    return f"{lower}..{upper}"


def format_count_range(values):
    lower, upper = values
    lower = int(math.ceil(lower))
    upper = "inf" if math.isinf(upper) else int(math.floor(upper))
    return f"{lower}..{upper}"


qc_plot_keys = ["n_features", "total", "pct_mt", "pct_rps"]
qc_plot_titles = [
    r"gene number",
    r"gene counts",
    r"mitochondrion proportion",
    r"ribosome proportion",
]


def plot_violin(adata, obs, ax, title=None, clip=(0, None), median=True):
    bt.omics.pl.distribution(
        adata,
        obs=obs,
        kind="violin",
        points=False,
        median=median,
        clip=clip,
        ax=ax,
        showextrema=False,
    )
    if title is not None:
        ax.set_title(title)
    return ax


def plot_qc_violins(adata, outfile):
    fig, axes = plt.subplots(nrows=1, ncols=len(qc_plot_keys), figsize=(12, 3))
    for ax, key, title in zip(axes, qc_plot_keys, qc_plot_titles):
        plot_violin(adata, key, ax=ax, title=title)
    fig.tight_layout()
    fig.savefig(outfile)
    plt.close(fig)


parser = argparse.ArgumentParser(
    prog="filter",
    description=(
        "Calculate metrics (proportions of genes encoding mitochondrial and "
        "ribosomal proteins, quality control metrics), assign cells to a cell "
        "cycle phase and filter low-quality genes and cells."
    ),
    usage=f"python {script_name} <FILE> <FILE> [--marker <FILE>] [<args>]",
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)",
)

parser.add_argument(
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing filtered counts (format: h5ad)",
)

parser.add_argument(
    "--marker",
    dest="marker_infile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="input file storing cell cycle phase markers (rds format)",
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
    help="maximum percentage of cell dropout required for a gene to pass filtering (default: 1)",
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
    help="minimum and maximum number of expressed cells required for a gene to pass filtering (default: [0, inf])",
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
    help="minimum and maximum number of counts required for a gene to pass filtering (default: [0, inf])",
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
    help="maximum percentage of gene dropout required for a cell to pass filtering (default: 1)",
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
    help="minimum and maximum number of expressed genes required for a cell to pass filtering (default: [0, inf])",
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
    help="minimum and maximum number of reads required for a cell to pass filtering (default: [0, inf])",
)

parser.add_argument(
    "--mad-deviation",
    dest="mad_deviation",
    type=float,
    nargs=2,
    required=False,
    default=[math.inf, math.inf],
    metavar="FLOAT",
    help="MAD factors used to drop cells with total reads below or above median +/- factor*MAD (default: [inf, inf])",
)

parser.add_argument(
    "--consistent-mad",
    dest="consistent_mad",
    action="store_true",
    required=False,
    help="use normalized median absolute deviation",
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
    help="maximum proportion of mitochondrial gene expression required for a cell to pass filtering (default: 1)",
)

parser.add_argument(
    "--organism",
    dest="organism",
    action=cli.Store_organism,
    default="mouse",
    required=False,
    help="gene-related organism (default: mouse)",
)

parser.add_argument(
    "--geneinfo-version",
    dest="geneinfo_version",
    action=cli.Store_version,
    allow_current=False,
    allow_bundled=True,
    allow_date=False,
    allow_path=True,
    required=False,
    default="bundled",
    help="NCBI gene_info source used for gene name standardization (default: bundled)",
)

args = parser.parse_args()

if any(v < 0 for v in args.mad_deviation):
    raise ValueError(f"expected positive values, but received {args.mad_deviation}")

outpath = Path(os.path.dirname(args.outfile))
if not outpath.exists():
    os.makedirs(outpath)

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")

adata = ad.read_h5ad(Path(f"{args.infile}").resolve())
genesyn = bt.resources.ncbi.genesyn(
    organism=args.organism,
    version=args.geneinfo_version,
)

std.print_info("standardizing gene names")
adata.var["symbol"] = list(adata.var.index)
for input_identifier_type in ["name", "gene_id", "ensembl_id"]:
    bt.omics.pp.convert_gene_identifiers(
        adata,
        axis="var",
        input_identifier_type=input_identifier_type,
        genesyn=genesyn,
        copy=False,
    )
bt.omics.pp.merge_duplicate_vars(
    adata,
    copy=False,
)

adata.var_names_make_unique()
bt.omics.pp.sort(adata, on="both", copy=False)

shape = {"init": adata.shape}

std.print_task("detecting mitochondrial genes")
bt.omics.pp.mitochondrial_genes(
    adata,
    index_type="name",
    key="mt",
    axis="var",
    copy=False,
    genesyn=genesyn,
)

std.print_task("detecting ribosomal genes")
bt.omics.pp.ribosomal_genes(
    adata,
    index_type="name",
    key="rps",
    axis="var",
    copy=False,
    genesyn=genesyn,
)

if args.marker_infile is None:
    std.print_warning("cannot classify cell cycle phases: marker file not specified")
else:
    std.print_task("classifying cells by cell-cycle phase")
    std.print_info(
        f"loading cell-cycle marker data (file={std.format_path(args.marker_infile)})"
    )
    parser = rdata.parser.parse_file(args.marker_infile)
    std.print_debug("decoding marker data (format=RDS)")
    marker_pairs = rdata.conversion.convert(parser)
    std.print_info("scoring cell cycle phases")
    marker_pairs = marker_pairs_converter(marker_pairs, genesyn, "official_name")
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=FutureWarning,
            module=r"pypairs(\.|$)",
        )
        scores = pypairs.pairs.cyclone(adata, marker_pairs)
    adata.obs.rename(
        columns={
            "pypairs_G1": "G1_score",
            "pypairs_S": "S_score",
            "pypairs_G2M": "G2M_score",
        },
        inplace=True,
    )

std.print_task("calculating quality control metrics")
bt.omics.pp.qc(
    adata,
    qc_vars=["mt", "rps"],
    percent_top=None,
    log1p=False,
    copy=False,
)

raw_plot = outpath / "raw-data.pdf"
std.print_info(f"plotting QC summaries (directory={os.path.relpath(outpath)})")
plot_qc_violins(adata, raw_plot)

cell_totals = adata.obs["total"].to_numpy()
mad = median_absolute_deviation(np.log(cell_totals), consistency=(args.consistent_mad))
reads = [
    np.exp(np.median(np.log(cell_totals)) - args.mad_deviation[0] * mad),
    np.exp(np.median(np.log(cell_totals)) + args.mad_deviation[1] * mad),
]
cell_reads = [
    max(args.cell_reads[0], reads[0]),
    min(args.cell_reads[1], reads[1]),
]

ylim = [0, round(math.ceil(max(cell_totals) + 1000), -3)]
fig, ax = plt.subplots(nrows=1, ncols=2)
plot_violin(adata, "total", ax=ax[0], clip="data", median=False)
ax[0].axhline(reads[0], linewidth=1.5, linestyle="--", color=bt.omics.pl.get_color("red"))
ax[0].axhline(reads[1], linewidth=1.5, linestyle="--", color=bt.omics.pl.get_color("red"))
ax[0].set_ylim(ylim)
ax[0].set(title="raw")

std.print_task(
    "filtering genes "
    f"(dropout<={1e2 * args.gene_dropout:g}%, "
    f"expressed_cells={format_range(args.gene_expression)}, "
    f"counts={format_range(args.gene_counts)})"
)

bt.omics.pp.filter_var(
    adata,
    "pct_dropout",
    lambda x: (x <= 1e2 * args.gene_dropout),
)

bt.omics.pp.filter_var(
    adata,
    "n_barcodes",
    lambda x: (x >= args.gene_expression[0]) & (x < args.gene_expression[1]),
)

bt.omics.pp.filter_var(
    adata,
    "total",
    lambda x: (x >= args.gene_counts[0]) & (x < args.gene_counts[1]),
)

std.print_task(
    "filtering cells "
    f"(dropout<={1e2 * args.cell_dropout:g}%, "
    f"expressed_genes={format_range(args.cell_expression)}, "
    f"reads={format_count_range(cell_reads)}, "
    f"mitochondria<{1e2 * args.mt:g}%)"
)

bt.omics.pp.filter_obs(
    adata,
    "n_features",
    lambda x: (x >= (1 - args.cell_dropout) * adata.n_vars),
)

bt.omics.pp.filter_obs(
    adata,
    "n_features",
    lambda x: (x >= args.cell_expression[0]) & (x < args.cell_expression[1]),
)

bt.omics.pp.filter_obs(
    adata,
    "total",
    lambda x: (x >= args.cell_reads[0]) & (x < args.cell_reads[1]),
)

bt.omics.pp.filter_obs(
    adata,
    "total",
    lambda x: (x >= reads[0]) & (x < reads[1]),
)

bt.omics.pp.filter_obs(
    adata,
    "pct_mt",
    lambda x: x < 1e2 * args.mt,
)

shape["final"] = adata.shape

std.print_result(
    format_filtering_coverage("genes", shape["final"][1], shape["init"][1])
)
std.print_result(
    format_filtering_coverage("cells", shape["final"][0], shape["init"][0])
)

plot_violin(adata, "total", ax=ax[1], clip="data", median=False)
ax[1].axhline(reads[0], linewidth=1.5, linestyle="--", color=bt.omics.pl.get_color("red"))
ax[1].axhline(reads[1], linewidth=1.5, linestyle="--", color=bt.omics.pl.get_color("red"))
ax[1].set_ylim(ylim)
ax[1].set(title="filtered")
fig.tight_layout()
plt.savefig(f"{outpath}/total-counts.pdf")

plot_qc_violins(adata, f"{outpath}/filtered-data.pdf")

if args.marker_infile:
    fig, ax = plt.subplots(nrows=1, ncols=1)
    ax = adata.obs.pypairs_cc_prediction.value_counts().plot.bar(rot=0)
    ax.set(xlabel="cell cycle phases")
    plt.savefig(f"{outpath}/cell-cycles-counting.pdf")

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
std.write_h5ad(adata, filename=args.outfile, compression="gzip")
