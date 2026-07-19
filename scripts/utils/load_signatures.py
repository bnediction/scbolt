#!/usr/bin/env python

import argparse
import json
import os
from pathlib import Path

import bonesistools as bt
import pandas as pd

from scbolt import cli, console


def file2signatures(file):
    signatures_d = dict()
    for sheetname, signature in file.items():
        if not sheetname == "Description":
            cell_type = sheetname.split(".txt", 1)[0]
            gene_symbols = [
                gene for gene in list(signature["Gene Symbol"]) if isinstance(gene, str)
            ]
            signatures_d[cell_type] = gene_symbols
    return signatures_d


def df2signatures(df):
    signatures_d = dict()
    for cell_type, signatures in df.items():
        gene_symbols = [gene for gene in signatures if isinstance(gene, str)]
        signatures_d[cell_type] = gene_symbols
    return signatures_d


script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="load_signatures",
    description="""Load signatures data from two files,
    one in a table format and the other one in list format.""",
    usage=f"python {script_name} --table-infile <FILE> --list-infile <FILE> --outfile <FILE>",
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    "--table-infile",
    dest="table_infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="input file storing table signatures (format: xlsx)",
)

parser.add_argument(
    "--list-infile",
    dest="list_infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="input file storing list signatures (format: xlsx)",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing signatures (format: json)",
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

outpath = os.path.dirname(args.outfile)
if not outpath:
    os.makedirs(outpath)

console.print_task(f"loading table signatures (file={console.format_path(args.table_infile)})")
table_signatures_df = pd.read_excel(io=args.table_infile, sheet_name=None)
table_signatures_d = file2signatures(table_signatures_df)

console.print_task(f"loading list signatures (file={console.format_path(args.list_infile)})")
list_signatures_df = pd.read_excel(io=args.list_infile, sheet_name=0)
list_signatures_df.columns = list(list_signatures_df.iloc[0])
list_signatures_df.drop([0, 1], axis=0, inplace=True)
list_signatures_d = df2signatures(list_signatures_df)

signatures_d = {**table_signatures_d, **list_signatures_d}

console.print_info("standardizing signature gene names")
identifiers = bt.resources.ncbi.identifiers(
    organism=args.organism,
    version=args.geneinfo_version,
)
for k, v in signatures_d.items():
    signatures_d[k] = identifiers(v)
signatures_d = {
    phenotype: signature for phenotype, signature in signatures_d.items() if signature
}

console.print_task(f"saving signatures (file={console.format_path(args.outfile)})")
with open(f"{args.outfile}", "w") as file:
    json.dump(signatures_d, file, indent=1)
