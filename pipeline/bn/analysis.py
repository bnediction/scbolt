#!/usr/bin/env python

from typing import Optional, List

import os, argparse
from pathlib import Path

from typing import Any

import pandas as pd

from colomoto import minibn
from colomoto.types import Hypercube
import mpbn

import networkx as nx
from grntools.grn import path_to_string

s = """data/rna/integrated/bonesis/inference/min/one-min.bnet
data/rna/integrated/bonesis/inference/min/analysis
--bin-bonesis data/rna/integrated/bonesis/inference/min/one-min.csv
--bin-metastates data/rna/integrated/binarization/cluster_bin_macrostates.csv
--init-states Prom2_ctrl Prom2_treated
--final-states Rep_ctrl Prom3_ctrl Rep_treated Gran2_treated"""

parser = argparse.ArgumentParser(
    prog="Boolean network statistical analysis",
    description="""Perform statistical analysis upon a Boolean network.
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
    "--bin-metastates",
    dest="bin_metastates",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="file containing partially binarized macrostates (csv format)"
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
    "--init-states",
    dest="init_states",
    type=str,
    required=True,
    nargs="+",
    metavar="LITERAL",
    help="names of the initial configurations"
)

parser.add_argument(
    "--final-states",
    dest="final_states",
    type=str,
    required=True,
    nargs="+",
    metavar="LITERAL",
    help="names of the final configurations"
)

args = parser.parse_args(s.split())
length_str = 30

def get_states(file: Path, init_state_names: Optional[List[str]]=None, final_state_names: Optional[List[str]]=None):
    states = pd.read_csv(file, index_col=0).fillna("*")
    init_states = {state_name: Hypercube(states.loc[:,state_name].to_dict()) for state_name in init_state_names} if init_state_names is not None else None
    final_states = {state_name: Hypercube(states.loc[:,state_name].to_dict()) for state_name in final_state_names} if final_state_names is not None else None
    return states, init_states, final_states

if not args.outpath.exists():
    os.makedirs(args.outpath)

bn = mpbn.MPBooleanNetwork.load(str(args.infile))
grn = bn.influence_graph()
nodes = set(grn.nodes)

bonesis_states, init_config, final_config = get_states(args.bin_bonesis, args.init_states, args.final_states)
metastates, init_metastates, final_metastates = get_states(args.bin_metastates, args.init_states, args.final_states)

_nodes_explained_by_data = nodes.intersection(set(metastates.index))
_nodes_explained_by_inference = nodes.difference(set(metastates.index))

for _metastates in [init_metastates, final_metastates]:
    for name, hypercube in _metastates.items():
        _metastates[name] = Hypercube({node: hypercube[node] for node in _nodes_explained_by_data})
        _metastates[name].update({node: "*" for node in _nodes_explained_by_inference})

cycles = nx.simple_cycles(grn)

print(f"{'cycles':-^{length_str}}\n")

with open(f"{args.outpath}/simple-cycles.txt", "w") as file:
    for cycle in cycles:
        cycle_str = path_to_string(grn, *cycle, cycle[0])
        file.write(f"{cycle_str}\n")
        print(cycle_str)

print(f"\n{'attractors':-^{length_str}}\n")

reachable_attractors = [Hypercube(attractor) for attractor in bn.attractors()]
print(f"number of attractors: {len(reachable_attractors)}")
for name, hypercube in final_metastates.items():
    matching_attractor_number = 0
    for attractor in reachable_attractors:
        if hypercube.match_partial_state(attractor):
            matching_attractor_number += 1
    print(f"attractors subcube of state {name}: {matching_attractor_number}")


reachable_attractors = {state_name: list(bn.attractors(reachable_from=init_config[state_name])) for state_name in args.init_states}
for state_name in args.init_states:
    print(f"From {state_name}:")
    print(f"number of reachable attractors: {len(reachable_attractors[state_name])}")
    print(f"attractors corresponding to Gran2_treated: {len(reachable_attractors[state_name])}")


# attractors = list(bn.attractors(reachable_from=init))

# macrostates = pd.read_csv(args.bin_macrostates, index_col=0)
# final_names_ctrl = ["Prom3_ctrl", "Rep_ctrl"]
# final_macrostates = macrostates.loc[final_names_ctrl,:].transpose().replace(float("nan"),"*").to_dict()
# 
# import mpsim