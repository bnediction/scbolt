#!/usr/bin/env python

import os, std
import argparse
import yaml
from pathlib import Path

import pandas as pd
import bonesistools as bt

import bonesis

bonesis.settings["quiet"] = True

from utils import get_cfg

parser = argparse.ArgumentParser(
    prog="specification",
    description=
"""
check whether the bonesis properties are well defined and converting model specifications (format yml) and binarized macrostates (format csv) into three files:
    - metastates (csv): binarized metastates
    - properties (txt): dynamic Boolean properties
    - genes (txt): genes to pass bonesis filtering
file storing model specifications (format yml) have to contain three keys:
    - states (association between macrostate names and metastate names)
    - bonesis (dynamic Boolean properties in bonesis syntax)
    - genes (gene list to pass bonesis filtering)
""",
    usage="python specification.py <FILE> <FILE> --metastates <FILE> --properties <FILE> --genes <FILE> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter
)

parser.add_argument(
    dest="model_specification",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing model specifications for bonesis (format: yml)"
)

parser.add_argument(
    "macrostates",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing partially binarized macrostates (format: csv)"
)

parser.add_argument(
    "--model",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    required=True,
    help="output file storing dynamic Boolean properties (format: txt)"
)

parser.add_argument(
    "--metastates",
    dest="metastates",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing partially binarized metastates (format: csv)"
)

parser.add_argument(
    "--mandatory-genes",
    dest="mandatory_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="output file storing mandatory genes, being forced to appear (format: json or txt)"
)

parser.add_argument(
    "--important-genes",
    dest="important_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="output file storing important genes, being prioritize to appear (format: json or txt)"
)

parser.add_argument(
    "--sep",
    dest="sep",
    type=str,
    required=False,
    default=",",
    metavar="CHAR",
    help="field delimiter for csv format (default: ',')"
)

parser.add_argument(
    "--organism",
    dest="organism",
    choices=["mouse","human","escherichia-coli"],
    default="mouse",
    required=False,
    metavar="[mouse|human|escherichia-coli]",
    help="gene-related organism (default: mouse)"
)

args = parser.parse_args()

if args.organism == "escherichia-coli":
    args.organism = "escherichia coli"

for outfile in [args.macrostates, args.model, args.mandatory_genes, args.important_genes]:
    if not Path(os.path.dirname(outfile)).exists():
        os.makedirs(Path(os.path.dirname(outfile)))

genesyn = bt.dbs.ncbi.GeneSynonyms(organism=args.organism)

std.print_task(f"loading json-formatted model specification file {str(args.model_specification)}")

with open(args.model_specification, "r") as file:
    specification = yaml.safe_load(file)

std.print_task(f"loading csv-formatted binarized macrostates file {str(args.macrostates)}")

macrostates_df = pd.read_csv(args.macrostates, index_col=0, sep=args.sep)

std.print_task(f"getting binarized states")

macrostates_df = macrostates_df.rename(
    index=dict((v,k) for k,v in specification["states"].items()),
    inplace=False
).loc[specification["states"].keys()]

macrostates_cfg = get_cfg(
    macrostates_df,
    axis="index",
    genesyn=genesyn
)

std.print_debug("checking dynamic Boolean properties")

pkn_options = {
    "canonic": True,
    "maxclause": 8,
}

grn = bt.dbs.collectri.load_grn(
    organism="mouse",
    gene_synonyms=genesyn
)

pkn = bonesis.domains.InfluenceGraph(grn, **pkn_options)
bo = bonesis.BoNesis(pkn, macrostates_cfg)

for property in specification["bonesis"]:
    try:
        eval(property)
    except:
        raise RuntimeError(f"invalid dynamic Boolean properties")

std.print_task(f"saving dynamic Boolean properties in {args.model}")

with open(args.model, "w") as file:
    for property in specification["bonesis"]:
        file.write(f"{property}\n")

std.print_task(f"saving binarized metastates in {args.metastates}")

macrostates_df.to_csv(
    args.metastates,
    sep=",",
    index=True
)

std.print_task(f"saving mandatory genes in {args.mandatory_genes}")

mandatory_genes = specification["mandatory_genes"] if specification["mandatory_genes"] is not None else []
mandatory_genes = genesyn.sequence_standardization(mandatory_genes)

with open(args.mandatory_genes, "w") as file:
    for gene in mandatory_genes:
        file.write(f"{gene}\n")

std.print_task(f"saving important genes in {args.important_genes}")

important_genes = specification["important_genes"] if specification["important_genes"] is not None else []
important_genes = genesyn.sequence_standardization(important_genes)

with open(args.important_genes, "w") as file:
    for gene in important_genes:
        file.write(f"{gene}\n")
