#!/usr/bin/env python

import os, argparse
from pathlib import Path

from typing import Any

import pandas as pd

from colomoto import minibn
import mpbn

import networkx as nx
from grntools.grn import path_to_string

s = """data/rna/integrated/bonesis/inference/min/one-min.bnet
data/rna/integrated/bonesis/inference/min/analysis
--bin-bonesis data/rna/integrated/bonesis/inference/min/one-min.csv
--bin-metastates data/rna/integrated/binarization/cluster_bin_macrostates.csv
--init-names Prom2_ctrl Prom2_treated"""

parser = argparse.ArgumentParser(
    prog="Boolean network statistical analysis",
    description="""Perform statistical analysis upon a single Boolean network.
    It encompasses cycle analysis, Most Permissive reachability and attractor properties""",
    usage="python cycles.py <FILE> <PATH> [<args>]"
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="Boolean network file (bnet format)"
)

parser.add_argument(
    "outpath",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "--bin-bonesis",
    dest="bin_bonesis",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="file containing Bonesis binarized macrostates (csv format)"
)

parser.add_argument(
    "--bin-metastates",
    dest="bin_metastates",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="file containing partially binarized macrostates (csv format)"
)

args = parser.parse_args(s.split())

if not args.outpath.exists():
    os.makedirs(args.outpath)

bn = mpbn.MPBooleanNetwork.load(str(args.infile))
grn = bn.influence_graph()
states_bonesis = pd.read_csv(args.bin_bonesis, index_col=0)
init_ctrl = states_bonesis.loc[:,args.init_names[0]].to_dict()
init_treated = states_bonesis.loc[:,args.init_names[1]].to_dict()

cycles = nx.simple_cycles(grn)

with open(f"{args.outpath}/simple-cycles.txt", "w") as file:
    for cycle in cycles:
        file.write(f"{path_to_string(grn, *cycle, cycle[0])}\n")

attractors = list(bn.attractors(reachable_from=init_ctrl))
attractors = list(bn.attractors(reachable_from=init_treated))

# attractors = list(bn.attractors(reachable_from=init))

macrostates = pd.read_csv(args.bin_macrostates, index_col=0)
final_names_ctrl = ["Prom3_ctrl", "Rep_ctrl"]
final_macrostates = macrostates.loc[final_names_ctrl,:].transpose().replace(float("nan"),"*").to_dict()

import mpsim