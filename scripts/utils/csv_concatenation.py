#!/usr/bin/env python

import os
import std
from pathlib import Path

import argparse
import cli

import pandas as pd

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="csv_concatenation",
    description="""Concatenate CSV files by rows or columns.""",
    usage=f"python {script_name} [-h] <FILE ...> [-o <FILE>] [--axis <row | column>] [--suffixes <LITERAL ...>] [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    dest="infiles",
    type=lambda x: Path(x).resolve(),
    action=cli.Required_length,
    min=2,
    metavar="FILE",
    help="input files storing tabular data (format: csv)",
)

parser.add_argument(
    "-o",
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default="results.csv",
    metavar="FILE",
    help="output CSV file (default: results.csv)",
)

parser.add_argument(
    "--axis",
    dest="axis",
    type=str,
    required=False,
    default="row",
    choices=["row", "column"],
    metavar="[row | column]",
    help="row- or column-wise concatenation (default: row)",
)

parser.add_argument(
    "--suffixes",
    dest="suffixes",
    type=str,
    required=False,
    action=cli.Required_length,
    min=2,
    metavar="LITERAL",
    default=None,
    help="suffixes added to row or column labels, ordered with input CSV files",
)

parser.add_argument(
    "--sep",
    dest="sep",
    type=str,
    required=False,
    default=",",
    metavar="CHAR",
    help="field delimiter for input CSV files (default: ',')",
)

parser.add_argument(
    "--transpose",
    dest="transpose",
    required=False,
    action="store_true",
    help="transpose rows and columns",
)

args = parser.parse_args()

std.print_task(
    f"loading CSV tables (files={', '.join(std.format_path(file) for file in args.infiles)})"
)
dfs = [pd.read_csv(file, index_col=0, sep=args.sep) for file in args.infiles]

if args.suffixes is not None:
    if len(args.infiles) != len(args.suffixes):
        raise argparse.ArgumentError(
            None, "infiles and --suffixes require the same number of values"
        )
    else:
        for i in range(len(dfs)):
            dfs[i] = dfs[i].add_suffix(
                f"{args.suffixes[i]}", axis=0 if args.axis == "row" else 1
            )

std.print_task(f"concatenating dataframes (axis={args.axis})")
df = pd.concat(dfs, axis=0 if args.axis == "row" else 1)

if args.transpose:
    df = df.transpose()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(os.path.dirname(args.outfile))

std.print_task(f"saving CSV table (file={std.format_path(args.outfile)})")
df.to_csv(args.outfile, sep=args.sep)
