#!/usr/bin/env python

import sys
import os, std
import argparse, cli
from pathlib import Path

from tqdm import tqdm

import pandas as pd

import networkx as nx
import bonesis
from bonesis.asp_encoding import clingo_encode

import bonesistools as bt

from utils import get_cfg

bonesis.settings["quiet"] = True

class ptqdm(tqdm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file = sys.stdout
        self.leave = False

def write_solution(solution, bn_filename, name):
    bn = solution[1]
    bn.save(bn_filename)
    df = pd.DataFrame(solution[2])
    df.to_csv(f"{name}.csv")
    noi = set(bn) - set(bn.constants())
    with open(f"{name}.noi.txt", "w") as fp:
        fp.write("".join([f"{n}\n" for n in noi]))
    ig = bn.influence_graph()
    nx.drawing.nx_pydot.write_dot(ig, f"{name}.dot")

def remove_strong_constraints(bo: bonesis.BoNesis):
    strong_constraint_indices = []
    for i, bo_property in enumerate(bo.manager.properties):
        str_property = bo_property[0]
        if str_property in ["final_nonreach", "all_fixpoints", "allreach"]:
            strong_constraint_indices.append(i)
    bo.manager.properties = [bo.manager.properties.copy()[i] for i in range(len(bo.manager.properties)) if i not in strong_constraint_indices]

parser = argparse.ArgumentParser(
    prog="inference",
    description=
    """
    infer Most Permissive Boolean Networks using bonesis paradigm.
    """,
    usage="python inference.py [filter-stage1|filter-stage2|one|one-min|one-sub] <FILE> --bin-metastate <FILE> [<args>]"
)

parser.add_argument(
    "action",
    metavar="[filter-stage1|filter-stage2|one|one-min|one-sub]",
    choices=["filter-stage1", "filter-stage2", "one", "one-min", "one-sub"]
)

parser.add_argument(
    "model",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file containing model specifications in Bonesis langage (txt format)"
)

parser.add_argument(
    "metastates",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing partially binarized metastates (format: csv)"
)

parser.add_argument(
    "--asp",
    dest="asp",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="output file storing asp command (format: sh)"
)

parser.add_argument(
    "--solution",
    dest="solution",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="output file storing bonesis solution"
)

parser.add_argument(
    "--filter-grn",
    dest="filter_grn",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="file with one node per line (txt format)"
)

parser.add_argument(
    "--mandatory-genes",
    dest="mandatory_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="input file storing mandatory genes, being forced to appear (format: json or txt)"
)

parser.add_argument(
    "--important-genes",
    dest="important_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="input file storing important genes, being prioritize to appear (format: json or txt)"
)

parser.add_argument(
    "--only-weak-constraints",
    dest="only_weak_constraints",
    required=False,
    action="store_true",
    help="filtering optimization only on weak constraints"
)

parser.add_argument(
    "--clingo-opt-strategy",
    dest="clingo_opt_strategy",
    type=str,
    help="clingo optimization strategy"
)

parser.add_argument(
    "--max-clause",
    dest="max_clause",
    type=int,
    required=False,
    default=8,
    metavar="INT",
    help="maximum number of literals/atoms in each propositional formula (default: 8)"
)

parser.add_argument(
    "--minimize-feedbacks",
    dest="minimize_feedbacks",
    required=False,
    action="store_true",
    help="minimize the number of length-one feedbacks"
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
    action=cli.Store_organism,
    default="mouse",
    required=False
)

args = parser.parse_args()

if not args.action.startswith("filter") and args.only_weak_constraints is True:
    raise argparse.ArgumentError(None, "option --only-weak-constraints not allowed when action is related to inference instead of filtering")

genesyn = bt.dbs.ncbi.GeneSynonyms(organism=args.organism)

std.print_task(f"loading partially binarized metastates-related file {str(args.metastates)}")

metastates_df = pd.read_csv(args.metastates, index_col=0, sep=args.sep)

metastates_cfg = get_cfg(
    metastates_df,
    axis="index",
    genesyn=genesyn
)

std.print_task("initializing bonesis settings")

pkn_options = {
    "canonic": False if args.action.startswith("filter") else True,
    "maxclause": args.max_clause,
}
if args.action == "filter-stage1":
    pkn_options["allow_skipping_nodes"] = True

grn = bt.dbs.collectri.load_grn(
    organism=args.organism,
    genesyn=genesyn
)

if args.filter_grn:
    with open(args.filter_grn) as fp:
        nodes = [line.strip() for line in fp.readlines()]
    grn = grn.subgraph(nodes)

pkn = bonesis.domains.InfluenceGraph(grn, **pkn_options)

bo = bonesis.BoNesis(pkn, metastates_cfg)

with open(args.model, "r") as file:
    for line in file:
        exec(line.rstrip('\n'))

if args.only_weak_constraints:
    remove_strong_constraints(bo)

if args.action == "filter-stage1":

    std.print_task("filtering genes by maximizing explanatory node number (stage 1)")
    
    bo.maximize_nodes()

    if args.mandatory_genes:
        with open(args.mandatory_genes) as file:
            mandatory_genes = [line.rstrip() for line in file.readlines()]
        mandatory_genes = genesyn(mandatory_genes)
        for gene in mandatory_genes:
            bo.custom(f"node({clingo_encode(gene)}).")

    if args.important_genes:
        with open(args.important_genes) as file:
            important_genes = [line.rstrip() for line in file.readlines()]
        important_genes = genesyn(important_genes)
        for node in important_genes:
            bo.custom("#maximize { 1@100,N: important_node(N),node(N) }.")

    def intermediate_solution(nodes):
        with open(args.solution, "w") as file:
            for node in nodes:
                file.write(f"{node}\n")

    view = bonesis.NodesView(
        bo,
        mode="optN",
        intermediate_model_cb=intermediate_solution,
        clingo_opt_strategy=args.clingo_opt_strategy or "bb,dec",
        progress=ptqdm
    )
    view.standalone(output_filename=args.asp)

    std.print_warning("this may take some time.")
    solution = next(iter(view))

    with open(args.solution, "w") as file:
        for node in solution:
            file.write(f"{node}\n")

    nodes_in_data = set()
    for bin_nodes in bo.data.values():
        nodes_in_data.update(bin_nodes.keys())
    nodes_in_domain = set(bo.domain.nodes)

    print("")
    std.print_result(f"node number: [data: {len(nodes_in_data)}, domain: {len(nodes_in_domain)}, solution: {len(solution)}]")
    std.print_result(f"node number: [kept in data: {len(nodes_in_data & solution)}, removed in data: {len(nodes_in_data - solution)}]")
    std.print_result(f"node number: [kept in domain: {len(nodes_in_domain & solution)}, removed in domain: {len(nodes_in_domain - solution)}]")

elif args.action == "filter-stage2":

    std.print_task("filtering genes by maximizing strong constant number (stage 2)")
    
    bo.maximize_strong_constants()
    if args.minimize_feedbacks:
        bo.custom("edge(A,A) :- clause(A,_,A,_). #minimize { 1@10000,A: edge(A,A) }.")

    view = bonesis.NonStrongConstantNodesView(
        bo,
        mode="optN",
        clingo_opt_strategy="usc",
        clingo_options=["--opt-usc-shrink=inv"],
        progress=ptqdm
    )
    view.standalone(output_filename=args.asp)

    std.print_warning("this may take some time.")
    solution = next(iter(view))

    with open(args.solution, "w") as file:
        for node in solution:
            file.write(f"{node}\n")
    
    nodes_in_data = set()
    for bin_nodes in bo.data.values():
        nodes_in_data.update(bin_nodes.keys())
    nodes_in_domain = set(bo.domain.nodes)

    print("")
    std.print_result(f"node number: [data: {len(nodes_in_data)}, domain: {len(nodes_in_domain)}, solution: {len(solution)}]")
    std.print_result(f"node number: [kept in data: {len(nodes_in_data & solution)}, removed in data: {len(nodes_in_data - solution)}]")
    std.print_result(f"node number: [kept in domain: {len(nodes_in_domain & solution)}, removed in domain: {len(nodes_in_domain - solution)}]")

elif args.action == "one":
    
    view = bonesis.InfluenceGraphView(
        bo,
        extra=("boolean-network", "configurations")
    )
    view.standalone(output_filename=args.asp)

    std.print_warning("this may take some time.")
    solution = next(iter(view))

    write_solution(
        solution,
        args.solution,
        f"{os.path.dirname(args.solution)}/one"
    )

elif args.action == "one-min":
    
    bo.custom("edge(A,B) :- clause(B,_,A,_). #minimize { 1@1,A,B: edge(A,B) }.")
    bo.custom("#maximize { 1@10,N: constant(N) }.")
    if args.minimize_feedbacks:
        bo.custom("#minimize { 1@100,A: edge(A,A) }.")

    view = bonesis.InfluenceGraphView(
        bo,
        mode="optN",
        clingo_opt_strategy="usc",
        extra=("boolean-network", "configurations"),
        progress=ptqdm
    )
    view.standalone(output_filename=args.asp)

    std.print_warning("this may take some time.")
    solution = next(iter(view))

    write_solution(
        solution,
        args.solution,
        f"{os.path.dirname(args.solution)}/one-min"
    )

elif args.action == "one-sub":
    
    view = bonesis.InfluenceGraphView(
        bo,
        solutions="subset-minimal",
        extra=("boolean-network", "configurations")
    )
    view.standalone(output_filename=args.asp)

    std.print_warning("this may take some time.")
    solution = next(iter(view))

    write_solution(
        solution,
        args.solution,
        f"{os.path.dirname(args.solution)}/one-sub"
    )

elif args.action == "sub":
    
    view = bonesis.InfluenceGraphView(
        bo,
        solutions="subset-minimal",
        extra=("boolean-network", "configurations")
    )
    view.standalone(output_filename=args.asp)

    std.print_warning("this may take some time.")
    for i, solution in enumerate(view):
        write_solution(
            solution,
            f"{os.path.dirname(args.solution)}/sub-{i}.bnet",
            f"{os.path.dirname(args.solution)}/sub-{i}"
        )
