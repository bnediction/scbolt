#!/usr/bin/env python

import warnings

import os
import std
import argparse
from pathlib import Path

from bonesistools.databases.ncbi import GeneSynonyms

import pandas as pd

parser = argparse.ArgumentParser(
    prog="gene name standardization",
    description="""Convert gene aliases by another aliases.
    By default, convert gene names by their NCBI reference names.""",
    usage="""python name_standardization.py [-h] <path> <path> [<args>]""",
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="infile in txt, csv or tsv format",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="outfile in same format as infile",
)

parser.add_argument(
    "-s",
    "--sep",
    dest="sep",
    type=str,
    default=",",
    required=False,
    metavar="CHAR",
    help="field delimiter for the outfile if extension infile is csv or tsv (default: `,`)",
)

parser.add_argument(
    "--axis",
    dest="axis",
    choices=["index", "columns"],
    default="index",
    required=False,
    metavar="[index | columns]",
    help="axis to change in dataframe instance if infile format is csv or tsv (default: index)",
)

parser.add_argument(
    "--organism",
    dest="organism",
    choices=["mouse", "human", "escherichia coli"],
    default="mouse",
    required=False,
    metavar="[mouse | human | escherichia coli]",
    help="gene-related organism (default: mouse)",
)

parser.add_argument(
    "--gene-type",
    dest="input_identifier_type",
    default="name",
    required=False,
    metavar="[name | gene_id | ensembl_id | <database>]",
    help="gene identifier input format (default: name)",
)

parser.add_argument(
    "--alias-type",
    dest="output_identifier_type",
    default="official_name",
    required=False,
    metavar="[official_name | gene_id | ensembl_id | <database>]",
    help="gene identifier output format (default: official_name)",
)

parser.add_argument(
    "-q",
    "--quiet",
    dest="quiet",
    required=False,
    action="store_true",
    help="hidden information about running programm",
)

args = parser.parse_args()

if args.quiet:
    warnings.filterwarnings("ignore")

if not Path(os.path.dirname(args.outfile)).exists:
    os.makedirs(os.path.dirname(args.outfile))

file_extension = str(args.infile).split(".")[-1]

genesynonyms = GeneSynonyms(organism=args.organism)

std.print_task(f"loading gene data from {str(args.infile)}")
std.print_info(
    f"standardizing gene identifiers ({args.input_identifier_type} => {args.output_identifier_type})"
)
if file_extension == "txt":
    with open(args.infile, "r") as file:
        gene_list = [line.replace("\n", "") for line in file]
    gene_list = genesynonyms(
        gene_list, input_type=args.input_type, output_type=args.output_type
    )
    with open(args.outfile, "w") as file:
        for gene in gene_list:
            file.write(f"{gene}\n")
elif file_extension == "csv" or file_extension == "tsv":
    output = pd.read_csv(args.infile, index_col=0, sep=args.sep)
    genesynonyms(
        output,
        input_identifier_type=args.input_type,
        output_identifier_type=args.output_type,
        axis=args.axis,
        copy=False,
    )
    output.to_csv(args.outfile, sep=args.sep)
else:
    raise IOError(f"incorrect format (txt, csv or tsv format expected)")

std.print_task(f"saving standardized gene data in {str(args.outfile)}")
