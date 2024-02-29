#!/usr/bin/env python

import sys
from pathlib import Path

import argparse

import pandas as pd

import decoupler as dc

import itertools
import networkx as nx
import bonesis as bo
from bonesis.asp_encoding import clingo_encode

bo.settings["quiet"] = True

def load_bin(file: Path) -> dict:
    meta_bin = pd.read_csv(file, index_col=0)
    return {config: genes.dropna().to_dict() for config, genes in meta_bin.iterrows()}

def collectri_to_grn(
    collectri: pd.DataFrame,
    sign_label: str = "weight",
    remove_pmid: bool = False
    ) -> nx.MultiDiGraph:
    if sign_label is not None:
        collectri = collectri.rename(columns = {sign_label:"sign"})
    if remove_pmid is True:
        remove_pmid = "PMID" in collectri.columns
    return nx.from_pandas_edgelist(
        df = collectri.drop("PMID", axis=1) if remove_pmid else collectri,
        source="source",
        target="target",
        edge_attr=True,
        create_using=nx.MultiDiGraph
    )

def bo_model(file: Path) -> None:
    with open(file, "r") as file:
        for line in file:
            eval(line)
    return None

class Arguments:
    def __init__(self):
        self.bin_file=Path("data/rna/binarization/cluster_bin_node_clusters.csv")
        self.branch_file=Path("data/rna/bonesis/bo_model.txt")
        self.action="filter_stage1"

args = Arguments()

parser = argparse.ArgumentParser()
parser.add_argument("--filter-grn", type=str, help="file with one node per line")
parser.add_argument("--force-nodes", type=str, help="json file with node list")
parser.add_argument("--maximize-important-nodes", action="store_true")
parser.add_argument("--force-important-nodes", action="store_true")
parser.add_argument("--clingo-opt-strategy", type=str)
parser.add_argument("action", choices=["filter_stage1", "filter_stage2", "one", "one-min", "one-sub"])
args = parser.parse_args()

collectri_db = dc.get_collectri(organism="mouse", split_complexes=True)
grn = collectri_to_grn(collectri_db, sign_label="weight", remove_pmid=True)
if args.filter_grn:
    with open(args.filter_grn) as fp:
        nodes = [l.strip() for l in fp.readlines()]
    grn = grn.subgraph(nodes)

print(f"GRN has {len(grn.nodes)} nodes and {len(grn.edges)} edges", file=sys.stderr)

pkn_options = {
    "canonic": True,
    "maxclause": 8,
}
if args.action.startswith("filter"):
    pkn_options["canonic"] = False
if args.action == "filter_stage1":
    pkn_options["allow_skipping_nodes"] = True

meta_bin = load_bin(args.bin_file)

pkn = bo.domains.InfluenceGraph(grn, **pkn_options)
bo = bo.BoNesis(pkn, meta_bin)
bo_model(args.branch_file)





import os, argparse
from pathlib import Path

import itertools
from functools import reduce

import pandas as pd

from networkx import MultiDiGraph
import mpbn

pluripotent = "LT_HSC"
stable_states = ['Bas_Mast', 'CFU_E', 'GMP', 'MDP', 'preDC']

with open("dorothea-20231104-ABC/missing_nodes.txt") as fp:
    missing_nodes = [l.strip() for l in fp]

important_nodes = [

]

def bomodel(bo):
    for fp in stable_states:
        ~bo.obs('LT_HSC') >= bo.fixed(~bo.obs(fp))
    for a, b in itertools.combinations(stable_states, 2):
        ~bo.obs(a) != ~bo.obs(b)
