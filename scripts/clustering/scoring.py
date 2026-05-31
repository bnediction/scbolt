#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import json
import pandas as pd
import anndata as ad
import bonesistools as bt
from anndata import AnnData


def multiple_hypergeometric_test(
    adata: AnnData, signatures: dict, markers: list
) -> dict:

    return {
        cell_type: bt.sct.tl.hypergeometric_test(adata, signature, markers)
        for cell_type, signature in signatures.items()
    }


parser = argparse.ArgumentParser(
    prog="scoring",
    description="Score signature-related phenotypes with respect to cell clusters.",
    usage="python scoring.py [-h] <FILE> <FILE> <FILE> <FILE> --cluster <LITERAL> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)",
)

parser.add_argument(
    "signatures",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing phenotype-gene list associations (format: json)",
)

parser.add_argument(
    "markers",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing gene sets for each spreadsheet (format: xlsx)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing signature-score associations (format: csv)",
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in 'adata.obs' distinguishing cell populations (required)",
)

parser.add_argument(
    "--ignore-sheets",
    dest="ignore_sheets",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="spreadsheet names to ignore (default: None)",
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")
adata = ad.read_h5ad(args.infile)

std.print_task(f"loading signature definitions (file={std.format_path(args.signatures)})")
with open(args.signatures, "r") as file:
    signatures = json.load(file)

std.print_task(f"loading marker workbook (file={std.format_path(args.markers)})")
with pd.ExcelFile(args.markers) as file:
    markers = {}
    for sheet_name in file.sheet_names:
        if sheet_name not in args.ignore_sheets:
            df = file.parse(sheet_name, header=None)
            markers[sheet_name] = df[df.columns[0]].to_list()

std.print_task("analyzing cell signatures")

std.print_debug("deleting signature genes (reason=absent_from_AnnData)")
background = adata.var_names
for phenotype, genes in signatures.items():
    signatures[phenotype] = {gene for gene in genes if gene in background}
signatures = {
    phenotype: signature for phenotype, signature in signatures.items() if signature
}

std.print_info("estimating hypergeometric distribution-based p-values")

info = dict()
for group in sorted(adata.obs[args.cluster].unique()):
    group_adata = adata[adata.obs[args.cluster] == group]
    group_info = dict()
    group_info["cells"] = group_adata.n_obs
    group_info["proportion"] = round(group_adata.n_obs / adata.n_obs, ndigits=6)
    group_info["median_expression"] = group_adata.obs["n_genes_by_counts"].median()
    group_info["median_reads"] = group_adata.obs["total_counts"].median()
    pvalues = multiple_hypergeometric_test(
        adata=group_adata, signatures=signatures, markers=markers[group]
    )
    group_info.update({k: round(v, ndigits=6) for k, v in pvalues.items()})
    info[group] = group_info
info = pd.DataFrame.from_dict(info)

std.print_result(f"signature summary\n{info}")

std.print_task(f"saving CSV table (file={std.format_path(args.outfile)})")
info.to_csv(args.outfile, sep=",", index=True)
