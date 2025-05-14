#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse, cli
from pathlib import Path

import math

import pandas as pd
import anndata as ad
import scanpy as sc
import bonesistools as bt
from pandas import ExcelWriter

parser = argparse.ArgumentParser(
    prog="markers",
    description=
    """
    Search for differentially expressed genes (markers) between clusters.
    """,
    usage="python markers.py [-h] <FILE> <FILE> [--xlsx <FILE>] --cluster <LITERAL> [<args>]"
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)"
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing marker-metric associations (format: csv)"
)

parser.add_argument(
    "--xlsx",
    dest="xlsx",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="output file storing differentially expressed genes, each spreadsheet being related to a cluster (format: xlsx)"
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in 'adata.obs' distinguishing cell populations (required)"
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used (if not specified, use adata.X; expected logarithmized data)"
)

parser.add_argument(
    "--are-log",
    dest="are_log",
    action="store_true",
    required=False,
    help="specify whether data are logarithmized"
)

parser.add_argument(
    "--logfc",
    dest="logfc",
    action=cli.Range,
    type=float,
    min=0,
    max=math.inf,
    required=False,
    default=0.25,
    help="minimum log2 fold-change for a gene to be considered as differentially expressed (default: 0.25)"
)

parser.add_argument(
    "--alpha",
    dest="alpha",
    action=cli.Range,
    type=float,
    min=0,
    max=1,
    required=False,
    default=0.05,
    help="significance level or probability of rejecting null hypothesis that gene is not differentially expressed (default: 0.05)"
)

parser.add_argument(
    "--correction",
    dest="correction",
    type=str,
    required=False,
    default="benjamini-hochberg",
    choices=["benjamini-hochberg","bonferroni"],
    metavar="[benjamini-hochberg|bonferroni]",
    help="method used for correcting the significance level (default: benjamini-hochberg)"
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading file {str(args.infile)}")

adata = ad.read_h5ad(args.infile)

if args.layer:
    adata.X = adata.layers[args.layer].copy()

std.print_task("ranking genes for characterizing groups")

sc.tl.rank_genes_groups(
    adata=adata,
    groupby=args.cluster,
    use_raw=False,
    layer=args.layer,
    reference="rest",
    method="wilcoxon",
    tie_correct=True,
    corr_method=args.correction
)
markers = bt.sct.tl.extract_rank_genes_groups(
    adata,
    logfc_keeping=False
)
markers = markers.loc[markers["adj_pvals"] < args.alpha]
std.print_warning("found inconsistencies between log2 fold-changes derived from seurat::FindAllMarkers and scanpy.rank_gene_groups (see <https://www.biostars.org/p/453129/>)")
std.print_debug("updating log2 fold-changes")
markers = bt.sct.tl.update_logfoldchanges(
    df=markers,
    adata=adata,
    layer=args.layer,
    groupby=args.cluster,
    is_log=True,
    cluster_rebalancing=False,
    threshold=args.logfc
)

std.print_task(f"saving data in {str(args.outfile)}")
markers.to_csv(
    args.outfile,
    sep=",",
    index=False
)

if args.xlsx:
    std.print_task(f"saving differentially expressed genes in {str(args.xlsx)}")
    with ExcelWriter(args.xlsx) as xlsx_writer:
        pd.DataFrame(adata.var_names).to_excel(
            xlsx_writer,
            sheet_name="background",
            header=False,
            index=False
        )
        for cluster in markers["clusters"].unique():
            markers[markers["clusters"] == cluster]["genes"].to_excel(
                xlsx_writer,
                sheet_name=cluster,
                header=False,
                index=False
            )
