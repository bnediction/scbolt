#!/usr/bin/env python

import os, std
import argparse, cli
import yaml
from typing import Optional, Sequence, cast
from pathlib import Path

import pandas as pd
import bonesistools as bt

import bonesis

bonesis.settings["quiet"] = True

from utils import get_cfg


def load_prior_network(
    domain,
    organism,
    genesyn,
    dorothea_levels: Optional[Sequence[str]] = None,
):
    if domain == "collectri":
        std.print_info(f"loading CollecTRI prior network (organism: {organism})")
        return bt.dbs.omnipath.load_collectri_grn(
            organism=organism,
            genesyn=genesyn,
        )
    if domain == "dorothea":
        levels = cast(list[str], dorothea_levels)
        std.print_info(
            f"loading DoRothEA prior network "
            f"(organism: {organism}, levels: {', '.join(levels)})"
        )
        return bt.dbs.omnipath.load_dorothea_grn(
            organism=organism,
            levels=levels,
            genesyn=genesyn,
        )
    std.print_info(f"loading custom prior network ({domain})")
    return bt.bpy.ig.read_interaction_graph(
        infile=domain,
        genesyn=genesyn,
    )


parser = argparse.ArgumentParser(
    prog="specification",
    description="""Check whether BoNesis properties are well defined and convert model specifications (format: yml) and binarized macrostates (format: csv) into four files:
    - model (txt): dynamic Boolean properties
    - metastates (csv): partially binarized metastates
    - important-genes (txt): genes prioritized to appear in Boolean network solutions
    - mandatory-genes (txt): genes forced to appear in Boolean network solutions

The model specification file (format: yml) must contain four keys:
    - states (list of metastate-macrostate name associations)
    - bonesis (list of dynamic Boolean properties in BoNesis syntax)
    - mandatory_genes (list of genes forced to appear in Boolean network solutions)
    - important_genes (list of genes prioritized to appear in Boolean network solutions)
""",
    usage="python specification.py <FILE> <FILE> --model <FILE> --metastates <FILE> --mandatory-genes <FILE> --important-genes <FILE> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    dest="model_specification",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing model specifications for BoNesis (format: yml)",
)

parser.add_argument(
    "macrostates",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing partially binarized macrostates (format: csv)",
)

parser.add_argument(
    "--model",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    required=True,
    help="output file storing dynamic Boolean properties (format: txt)",
)

parser.add_argument(
    "--metastates",
    dest="metastates",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing partially binarized metastates (format: csv)",
)

parser.add_argument(
    "--filter-genes",
    dest="filter_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="input file storing genes of interest to pass filtering (if not specified, all genes are considered)",
)

parser.add_argument(
    "--important-genes",
    dest="important_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="output file storing important genes prioritized to appear (format: json or txt)",
)

parser.add_argument(
    "--mandatory-genes",
    dest="mandatory_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="output file storing mandatory genes forced to appear (format: json or txt)",
)

parser.add_argument(
    "--domain",
    dest="domain",
    action=cli.Bonesis_domain,
    required=False,
    default="collectri",
)

parser.add_argument(
    "--sep",
    dest="sep",
    type=str,
    required=False,
    default=",",
    metavar="CHAR",
    help="field delimiter for csv format (default: ',')",
)

parser.add_argument(
    "--organism",
    dest="organism",
    action=cli.Store_organism,
    default="mouse",
    required=False,
)

parser.add_argument(
    "--dorothea-levels",
    dest="dorothea_levels",
    nargs="+",
    choices=["A", "B", "C", "D"],
    default=["A", "B", "C"],
    metavar="[A | B | C | D]",
    help="DoRothEA confidence levels used when --domain dorothea (default: A B C)",
)

args = parser.parse_args()

for outfile in [
    args.macrostates,
    args.model,
    args.mandatory_genes,
    args.important_genes,
]:
    if not Path(os.path.dirname(outfile)).exists():
        os.makedirs(Path(os.path.dirname(outfile)))

genesyn = bt.dbs.ncbi.GeneSynonyms(organism=args.organism)

std.print_task(
    f"loading json-formatted model specification file {str(args.model_specification)}"
)

with open(args.model_specification, "r") as file:
    specification = yaml.safe_load(file)

std.print_task(
    f"loading csv-formatted binarized macrostates file {str(args.macrostates)}"
)

macrostates_df = genesyn(
    pd.read_csv(args.macrostates, index_col=0, sep=args.sep), axis="columns"
)

std.print_task("getting binarized states")

important_genes = (
    set(specification["important_genes"])
    if specification["important_genes"] is not None
    else set()
)
important_genes = genesyn(important_genes)

mandatory_genes = (
    set(specification["mandatory_genes"])
    if specification["mandatory_genes"] is not None
    else set()
)
mandatory_genes = genesyn(mandatory_genes)

if args.filter_genes:
    std.print_info("filtering genes")
    with open(args.filter_genes) as file:
        keep_only = {line.strip() for line in file.readlines()}
    keep_only = genesyn(keep_only)
    if important_genes - keep_only:
        std.print_debug(
            "some important genes have been filtered out but are reintegrated: {0}".format(
                ", ".join(f"{gene}" for gene in list(important_genes - keep_only))
            )
        )
    if mandatory_genes - keep_only:
        std.print_debug(
            "some mandatory genes have been filtered out but are reintegrated: {0}".format(
                ", ".join(f"{gene}" for gene in list(mandatory_genes - keep_only))
            )
        )
    keep_only = keep_only | mandatory_genes | important_genes
    keep_only_present = keep_only & set(macrostates_df.columns)
    if keep_only - keep_only_present:
        std.print_warning(
            "some important and/or mandatory genes are missing in csv-formatted binarized macrostate file: {0}".format(
                ", ".join(f"{gene}" for gene in list(keep_only - keep_only_present))
            )
        )
    macrostates_df = macrostates_df.loc[:, list(keep_only_present)]

if specification["states"] is not None:
    macrostates_df.rename(
        index=dict((v, k) for k, v in specification["states"].items()), inplace=True
    )

macrostates_cfg = get_cfg(macrostates_df, axis="index", genesyn=genesyn)

std.print_info("checking Boolean properties")

grn = load_prior_network(args.domain, args.organism, genesyn, args.dorothea_levels)
pkn_options = {
    "canonic": True,
    "maxclause": 8,
}
pkn = bonesis.domains.InfluenceGraph(grn, **pkn_options)
bo = bonesis.BoNesis(pkn, macrostates_cfg)

for property in specification["bonesis"]:
    try:
        exec(property)
    except:
        raise RuntimeError(f"invalid dynamical Boolean properties: {property}")

std.print_task(f"saving dynamical Boolean properties in {args.model}")

with open(args.model, "w") as file:
    for property in specification["bonesis"]:
        file.write(f"{property}\n")

std.print_task(f"saving binarized metastates in {args.metastates}")

macrostates_df.to_csv(args.metastates, sep=",", index=True)

std.print_task(f"saving important genes in {args.important_genes}")

with open(args.important_genes, "w") as file:
    for gene in important_genes:
        file.write(f"{gene}\n")

std.print_task(f"saving mandatory genes in {args.mandatory_genes}")

with open(args.mandatory_genes, "w") as file:
    for gene in mandatory_genes:
        file.write(f"{gene}\n")
