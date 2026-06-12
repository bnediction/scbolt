#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

import anndata as ad
import pandas as pd


script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="annotation",
    description=(
        "Rename labels using user-defined names.\n"
        "Values passed to --labels must follow the syntax <old_name>:<new_name>."
    ),
    usage=f"python {script_name} [-h] <FILE> <FILE> --obs <LITERAL> --labels <LITERAL:LITERAL [LITERAL:LITERAL ...]>",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing counts with renamed labels (format: h5ad)",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in adata.obs where category names are redefined",
)

parser.add_argument(
    "--new-obs",
    dest="new_obs",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="if specified, create a new adata.obs column storing renamed labels",
)

parser.add_argument(
    "--labels",
    dest="labels",
    action=cli.Store_dict,
    nargs="+",
    required=True,
    help="mapping between old and new labels",
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

dict_to_str = ""
add = ""
for k, v in args.labels.items():
    dict_to_str += f"{add}{k}=>{v}"
    add = ", "

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")

adata = ad.read_h5ad(args.infile)

if args.obs not in adata.obs:
    raise KeyError(f"column '{args.obs}' not found in adata.obs")
elif not hasattr(adata.obs[args.obs], "cat"):
    raise ValueError(
        f"series 'adata.obs[{args.obs}]' does not refer to a categorical variable"
    )

std.print_task(f"renaming labels (column={args.obs}, labels={dict_to_str})")

categories = list(adata.obs[args.obs].cat.categories)
category_by_name = {str(category): category for category in categories}
missing_labels = sorted(set(args.labels) - set(category_by_name))
if missing_labels:
    raise KeyError(
        "labels not found in categorical column "
        f"'{args.obs}': {', '.join(missing_labels)}"
    )

labels = {category_by_name[key]: value for key, value in args.labels.items()}
renamed_values = adata.obs[args.obs].astype(object).replace(labels)
renamed_categories = []
for category in categories:
    renamed_category = labels.get(category, category)
    if renamed_category not in renamed_categories:
        renamed_categories.append(renamed_category)
renamed_labels = pd.Categorical(
    renamed_values,
    categories=renamed_categories,
    ordered=adata.obs[args.obs].cat.ordered,
)
if args.new_obs is None:
    adata.obs[args.obs] = renamed_labels
else:
    adata.obs[args.new_obs] = renamed_labels

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
std.write_h5ad(adata, filename=args.outfile, compression="gzip")
