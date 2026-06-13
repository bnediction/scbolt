#!/usr/bin/env python

import os
import std
import argparse
from pathlib import Path

import bonesistools as bt

import pandas as pd

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="genename_standardization",
    description="""Convert gene aliases to another identifier type.
    By default, convert gene names to their NCBI reference names.""",
    usage=f"""python {script_name} [-h] <PATH> <PATH> [<args>]""",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="input file storing gene identifiers (format: txt, csv or tsv)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output file storing standardized gene identifiers (same format as input file)",
)

parser.add_argument(
    "-s",
    "--sep",
    dest="sep",
    type=str,
    default=",",
    required=False,
    metavar="CHAR",
    help="field delimiter for CSV/TSV files (default: ',')",
)

parser.add_argument(
    "--axis",
    dest="axis",
    choices=["index", "columns"],
    default="index",
    required=False,
    metavar="[index | columns]",
    help="dataframe axis to standardize when input format is CSV or TSV (default: index)",
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
    help="hide runtime warnings",
)

args = parser.parse_args()

if args.quiet:
    import warnings

    warnings.filterwarnings("ignore")

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(os.path.dirname(args.outfile))

file_extension = str(args.infile).split(".")[-1]

genesynonyms = bt.dbs.ncbi.genesyn(organism=args.organism)

std.print_task(f"loading gene data (file={std.format_path(args.infile)})")
std.print_info(
    f"standardizing gene identifiers "
    f"({args.input_identifier_type} -> {args.output_identifier_type})"
)
if file_extension == "txt":
    with open(args.infile, "r") as file:
        gene_list = [line.replace("\n", "") for line in file]
    gene_list = genesynonyms(
        gene_list,
        input_identifier_type=args.input_identifier_type,
        output_identifier_type=args.output_identifier_type,
    )
    with open(args.outfile, "w") as file:
        for gene in gene_list:
            file.write(f"{gene}\n")
elif file_extension == "csv" or file_extension == "tsv":
    output = pd.read_csv(args.infile, index_col=0, sep=args.sep)
    genesynonyms(
        output,
        input_identifier_type=args.input_identifier_type,
        output_identifier_type=args.output_identifier_type,
        axis=args.axis,
        copy=False,
    )
    output.to_csv(args.outfile, sep=args.sep)
else:
    raise IOError("incorrect format (txt, csv or tsv format expected)")

std.print_task(f"saving standardized gene data (file={std.format_path(args.outfile)})")
