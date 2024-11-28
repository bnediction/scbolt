#!/usr/bin/env python

import os
from pathlib import Path

from typing import Optional

import argparse
from utils.argtype import Required_length

import pandas as pd

parser = argparse.ArgumentParser(
    prog="Row-wise concatenation",
    description="""csv file concatenation based on rows""",
    usage="python row_wise_concatenation.py [-h] <FILE ...> [--suffix <LITERAL ...>]"
)

parser.add_argument(
    dest="infiles",
    type=lambda x: Path(x).resolve(),
    action=Required_length,
    min=2,
    metavar="FILE",
    help="input csv files"
)

parser.add_argument(
    "--suffixes",
    dest="suffixes",
    type=str,
    required=False,
    action=Required_length,
    min=2,
    metavar="LITERAL",
    default=None,
    help="add suffixes to each row names (ordered with csv files)"
)

parser.add_argument(
    "--sep",
    dest="sep",
    type=str,
    required=False,
    default=",",
    metavar="CHAR",
    help="field delimiter for csv infiles (default: `,`)"
)

parser.add_argument(
    "-o", "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default="results.csv",
    metavar="FILE",
    help="output csv file (default: results.csv)"
)

args = parser.parse_args()

dfs = [pd.read_csv(file, index_col=0, sep=args.sep) for file in args.infiles]

if args.suffixes is not None:
    if len(args.infiles) != len(args.suffixes):
        raise argparse.ArgumentError(None, "infiles and --suffixes require the same number of values")
    else:
        for df, suffix in zip(dfs, args.suffixes):
            df.set_index(df.index.astype(str) + f"_{suffix}", inplace=True)

df = pd.concat(dfs, axis=0)

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(os.path.dirname(args.outfile))

df.to_csv(args.outfile, sep=args.sep)
