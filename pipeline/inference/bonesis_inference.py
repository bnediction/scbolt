#!/usr/bin/env python

import sys
import os
import json
from pathlib import Path
from argparse import ArgumentParser
from utils.argtype import Store_organism

from tqdm import tqdm

import pandas as pd

import networkx as nx
import bonesis
from bonesis.asp_encoding import clingo_encode

from bonesis_model import (
    bomodel,
    load_bin
)

from databases.collectri import load_grn
from databases.genesyn import GeneSynonyms

def write_solution(solution, name):
    f = solution[1]
    f.save(f"{name}.bn")
    df = pd.DataFrame(solution[2])
    df.to_csv(f"{name}.csv")
    noi = set(f) - set(f.constants())
    with open(f"{name}.noi.txt", "w") as fp:
        fp.write("".join([f"{n}\n" for n in noi]))
    ig = f.influence_graph()
    nx.drawing.nx_pydot.write_dot(ig, f"{name}.dot")

parser = ArgumentParser(
    prog="Boolean network inference",
    description="""From binarized meta-observations and specified trajectories,
    infer a Most Permissive Boolean Network""",
    usage="""python infer_bo.py [-h] <action> <path> --bin-metastate <path> [<args>]"""
)

parser.add_argument(
    "action",
    metavar="[filter-stage1 | filter-stage2 | one | one-min | one-sub]",
    choices=["filter-stage1", "filter-stage2", "one", "one-min", "one-sub"]
)

parser.add_argument(
    dest="outpath",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "--organism",
    dest="organism",
    action=Store_organism,
    default="mouse",
    required=False,
)

parser.add_argument(
    "--bin-metastates",
    dest="bin_metastates",
    type=lambda x: Path(x).resolve(),
    nargs="+",
    required=True,
    metavar="PATH",
    help="file(s) with binarized clusters"
)

parser.add_argument(
    "--model-specification",
    dest="model_specification",
    type=lambda x: Path(x).resolve(),
    required=True,
    nargs="+",
    metavar="PATH",
    help="file with binarized clusters"
)

parser.add_argument(
    "--filter-grn",
    dest="filter_grn",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="PATH",
    help="file with one node per line"
)

parser.add_argument(
    "--force-nodes",
    dest="force_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="PATH",
    help="json or txt file with node list, each nodes being forced to appear"
)

parser.add_argument(
    "--important-nodes",
    dest="important_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="PATH",
    help="json or txt file with node list, each nodes being prioritize to appear"
)

parser.add_argument(
    "--clingo-opt-strategy",
    dest="clingo_opt_strategy",
    type=str
)

parser.add_argument(
    "--verbose",
    dest="verbose",
    required=False,
    action="store_true"
)

args = parser.parse_args()

if not args.outpath.exists():
    os.makedirs(args.outpath)

if len(args.bin_metastates) != len(args.model_specification):
    raise ValueError(f"--bin-metastates and --model-specification does not specify the same number of files")

bonesis.settings["quiet"] = not args.verbose

pkn_options = {
    "canonic": True,
    "maxclause": 8,
}
if args.action.startswith("filter"):
    pkn_options["canonic"] = False
if args.action == "filter-stage1":
    pkn_options["allow_skipping_nodes"] = True

gene_synonyms = GeneSynonyms()

grn = load_grn(organism=args.organism, gene_synonyms=gene_synonyms)
if args.filter_grn:
    with open(args.filter_grn) as fp:
        nodes = [line.strip() for line in fp.readlines()]
    grn = grn.subgraph(nodes)

if args.verbose:
    print(f"GRN: {len(grn.nodes)} nodes, {len(grn.edges)} edges", file=sys.stderr)

meta_bin = load_bin(args.bin_metastates, gene_synonyms = gene_synonyms)

pkn = bonesis.domains.InfluenceGraph(grn, **pkn_options)
bo = bonesis.BoNesis(pkn, meta_bin)
bomodel(bo, args.model_specification)

if args.action == "filter-stage1":
    
    bo.maximize_nodes()

    if args.force_nodes:
        try:
            with open(args.force_nodes) as file:
                forced_nodes = list(json.load(file).keys())
        except:
            with open(args.force_nodes) as file:
                forced_nodes = [line.rstrip() for line in file.readlines()]
        forced_nodes = gene_synonyms.sequence_standardization(forced_nodes)
        for node in forced_nodes:
            bo.custom(f"node({clingo_encode(node)}).")

    if args.important_nodes:
        try:
            with open(args.important_nodes) as file:
                priority_nodes = list(json.load(file).keys())
        except:
            with open(args.important_nodes) as file:
                priority_nodes = [line.rstrip() for line in file.readlines()]
        priority_nodes = gene_synonyms.sequence_standardization(priority_nodes)
        for node in priority_nodes:
            bo.custom("#maximize { 1@100,N: important_node(N),node(N) }.")

    def interm_solution(nodes):
        with open(f"{args.outpath}/filter-stage1.json", "w") as fp:
            json.dump(list(sorted(nodes)), fp, indent=2)

    clingo_opt_strategy = args.clingo_opt_strategy or "bb,dec"
    view = bonesis.NodesView(bo, mode="optN", progress=tqdm,
                                intermediate_model_cb=interm_solution,
                                clingo_opt_strategy=clingo_opt_strategy)
    view.standalone(output_filename=f"{args.outpath}/filter-stage1.sh")
    solution = next(iter(view))
    for node in solution:
        print(node)

elif args.action == "filter-stage2":
    
    bo.maximize_strong_constants()
    view = bonesis.NonStrongConstantNodesView(bo, mode="optN",
                                  clingo_opt_strategy="usc",
                                  clingo_options=["--opt-usc-shrink=inv"])
    view.standalone(output_filename=f"{args.outpath}/filter-stage2.sh")
    solution = next(iter(view))
    for node in solution:
        print(node)

elif args.action == "one":
    
    view = bonesis.InfluenceGraphView(bo, extra=("boolean-network", "configurations"))
    solution = next(iter(view))
    write_solution(solution, f"{args.outpath}/bn-1")

elif args.action == "one-min":
    
    bo.custom("edge(A,B) :- clause(B,_,A,_). #minimize { 1@1,A,B: edge(A,B) }.")
    bo.custom("#maximize { 1@10,N: constant(N) }.")
    view = bonesis.InfluenceGraphView(bo, mode="optN", clingo_opt_strategy="usc",
                                      extra=("boolean-network",
                                             "configurations"),
                                      progress=tqdm)
    view.standalone(output_filename=f"{args.outpath}/one-min.sh")
    solution = next(iter(view))
    write_solution(solution, f"{args.outpath}/min-1")

elif args.action == "one-sub":
    
    view = bonesis.InfluenceGraphView(bo, solutions="subset-minimal", extra=("boolean-network", "configurations"))
    view.standalone(output_filename=f"{args.outpath}/one-sub.sh")
    solution = next(iter(view))
    write_solution(solution, f"{args.outpath}/sub-1")
