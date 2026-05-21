#!/usr/bin/env python

import os
import std
import argparse
import json
from pathlib import Path

import bonesistools as bt
import pandas as pd


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


parser = argparse.ArgumentParser(
    prog="Load signatures data",
    description="""Load signatures data from two files,
    one in a table format and the other one in list format.""",
    usage="python load_signatures.py <args>",
)

parser.add_argument(
    "--table-infile",
    dest="table_infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="path to table signatures file",
)

parser.add_argument(
    "--list-infile",
    dest="list_infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="path to list signatures file",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="output file",
)

args = parser.parse_args()

outpath = os.path.dirname(args.outfile)
if not outpath:
    os.makedirs(outpath)

std.print_task(f"loading table signatures from {str(args.table_infile)}")
table_signatures_df = pd.read_excel(io=args.table_infile, sheet_name=None)
table_signatures_d = file2signatures(table_signatures_df)

std.print_task(f"loading list signatures from {str(args.list_infile)}")
list_signatures_df = pd.read_excel(io=args.list_infile, sheet_name=0)
list_signatures_df.columns = list(list_signatures_df.iloc[0])
list_signatures_df.drop([0, 1], axis=0, inplace=True)
list_signatures_d = df2signatures(list_signatures_df)

signatures_d = {**table_signatures_d, **list_signatures_d}

std.print_info("standardizing signature gene names")
genesyn = bt.dbs.ncbi.GeneSynonyms()
for k, v in signatures_d.items():
    signatures_d[k] = genesyn(v)
signatures_d = {
    phenotype: signature for phenotype, signature in signatures_d.items() if signature
}

std.print_task(f"saving signatures in {str(args.outfile)}")
with open(f"{args.outfile}", "w") as file:
    json.dump(signatures_d, file, indent=1)
