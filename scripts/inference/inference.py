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

def write_bn_solution(
    solution,
    filenames_without_extension,
    noi_file=True,
    draw_ig=True
):
    bn = solution[1]
    bn.save(f"{filenames_without_extension}.bnet")
    df = pd.DataFrame(solution[2])
    df.to_csv(f"{filenames_without_extension}.csv")
    if noi_file is True:
        noi = set(bn) - set(bn.constants())
        with open(f"{filenames_without_extension}.noi.txt", "w") as fp:
            fp.write("".join([f"{n}\n" for n in noi]))
    dot = bt.bpy.bn_to_pydot(bn)
    dot.write_raw(f"{filenames_without_extension}.dot")
    if draw_ig is True:
        dot.write_pdf(f"{filenames_without_extension}.pdf")

def remove_hard_constraints(bo: bonesis.BoNesis):
    hard_constraint_indices = []
    for i, bo_property in enumerate(bo.manager.properties):
        str_property = bo_property[0]
        if str_property in ["final_nonreach", "all_fixpoints", "allreach"]:
            hard_constraint_indices.append(i)
    bo.manager.properties = [bo.manager.properties.copy()[i] for i in range(len(bo.manager.properties)) if i not in hard_constraint_indices]

parser_description = """
Infer Most Permissive Boolean Networks using bonesis paradigm. \
Four actions are proposed:
    - filter-stage1: component selection maximizing variable number while constraining Boolean networks to be compatible with the observations
    - filter-stage2: component selection deleting strong constants while constraining Boolean networks to be compatible with the observations
    - one-min: solution of Boolean network minimizing the edge number
    - all-sub: diverse solutions of Boolean network
See Chevalier et al. (2024) <https://hal.science/hal-04629083/document>.
"""

parser = argparse.ArgumentParser(
    prog="inference",
    description=parser_description,
    usage="python inference.py [filter-stage1 | filter-stage2 | one-min | all-sub] <FILE> <FILE> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter
)

parser.add_argument(
    "action",
    choices=["filter-stage1", "filter-stage2", "one-min", "all-sub"],
    metavar="[filter-stage1 | filter-stage2 | one-min | all-sub]"
)

parser.add_argument(
    "model",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file containing model specifications in Bonesis langage (format: txt)"
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
    metavar="FILE | PATH",
    help="output file storing bonesis solution (format: txt for 'filter-stage1'/'filter-stage2', bnet for 'one-min' or path for 'one-sub')"
)

parser.add_argument(
    "--database",
    dest="database",
    choices=["collectri", "dorothea"],
    required=False,
    default="collectri",
    metavar="[collectri | dorothea]",
    help="prior gene regulatory network defining the domain (search space)"
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
    "--only-soft-constraints",
    dest="only_soft_constraints",
    required=False,
    action="store_true",
    help="filtering optimization only on soft constraints"
)

parser.add_argument(
    "--clingo-opt-mode",
    dest="clingo_opt_mode",
    action=cli.Clingo_opt_mode,
    required=False,
    default="optN"
)

parser.add_argument(
    "--clingo-opt-strategy",
    dest="clingo_opt_strategy",
    action=cli.Clingo_opt_strategy,
    required=False
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

if not args.action.startswith("filter") and args.only_soft_constraints is True:
    raise argparse.ArgumentError(None, "option --only-soft-constraints not allowed when action is related to inference instead of filtering")

genesyn = bt.dbs.ncbi.GeneSynonyms(organism=args.organism)

std.print_task(f"loading partially binarized metastates-related file {str(args.metastates)}")

metastates_df = pd.read_csv(args.metastates, index_col=0, sep=args.sep).fillna(float("nan"))

metastates_cfg = get_cfg(
    metastates_df,
    axis="index"
)

std.print_task("initializing bonesis settings")

pkn_options = {
    "canonic": False if args.action.startswith("filter") else True,
    "maxclause": args.max_clause,
}
if args.action == "filter-stage1":
    pkn_options["allow_skipping_nodes"] = True

if args.database == "collectri":
    grn = bt.dbs.omnipath.load_collectri_grn(
        organism=args.organism,
        genesyn=genesyn
    )
else:
    grn = bt.dbs.omnipath.load_dorothea_grn(
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

if args.only_soft_constraints:
    remove_hard_constraints(bo)

if args.action == "filter-stage1":

    std.print_task("filtering components by maximizing variable number while constraining Boolean networks to be compatible with the observations")
    
    bo.maximize_nodes()

    if args.mandatory_genes:
        with open(args.mandatory_genes) as file:
            mandatory_genes = [line.rstrip() for line in file.readlines()]
        for gene in mandatory_genes:
            bo.custom(f"node({clingo_encode(gene)}).")

    if args.important_genes:
        with open(args.important_genes) as file:
            important_genes = [line.rstrip() for line in file.readlines()]
        for gene in important_genes:
            bo.custom(f"important_node({clingo_encode(gene)}).")
    
    bo.custom("#maximize { 1@100,N: important_node(N),node(N) }.")
    
    def intermediate_solution(nodes):
        with open(args.solution, "w") as file:
            for node in nodes:
                file.write(f"{node}\n")

    view = bonesis.NodesView(
        bo,
        mode=args.clingo_opt_mode,
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

    std.print_task("filtering components by deleting strong constants while constraining Boolean networks to be compatible with the observations")
    
    bo.maximize_strong_constants()
    if args.minimize_feedbacks:
        bo.custom("edge(A,A) :- clause(A,_,A,_). #minimize { 1@10000,A: edge(A,A) }.")

    view = bonesis.NonStrongConstantNodesView(
        bo,
        mode=args.clingo_opt_mode,
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

    write_bn_solution(
        solution,
        args.solution,
        f"{os.path.dirname(args.solution)}/one"
    )

elif args.action == "one-min":

    std.print_task("computing solution of Boolean network minimizing the edge number")
    
    bo.custom("edge(A,B) :- clause(B,_,A,_). #minimize { 1@1,A,B: edge(A,B) }.")
    bo.custom("#maximize { 1@10,N: constant(N) }.")
    if args.minimize_feedbacks:
        bo.custom("#minimize { 1@100,A: edge(A,A) }.")

    view = bonesis.InfluenceGraphView(
        bo,
        mode=args.clingo_opt_mode,
        clingo_opt_strategy="usc",
        extra=("boolean-network", "configurations"),
        progress=ptqdm
    )
    view.standalone(output_filename=args.asp)

    std.print_warning("this may take some time.")
    solution = next(iter(view))

    write_bn_solution(
        solution=solution,
        filenames_without_extension=f"{os.path.splitext(args.solution)[0]}"
    )

elif args.action == "all-sub":

    std.print_task("sampling diverse solutions of Boolean network")
    
    view = bonesis.InfluenceGraphView(
        bo,
        solutions="subset-minimal",
        extra=("boolean-network", "configurations"),
        progress=ptqdm
    )
    view.standalone(output_filename=args.asp)

    std.print_warning("this may take some time.")
    for i, solution in enumerate(tqdm(view)):
        os.makedirs(f"{args.solution}/{i}")
        write_bn_solution(
            solution=solution,
            filenames_without_extension=f"{args.solution}/{i}/one_sub",
            noi_file=False
        )
