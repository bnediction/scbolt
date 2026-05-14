#!/usr/bin/env python

from typing import Optional

import sys
import datetime
import os, std
import argparse, cli
from pathlib import Path

import re

from tqdm import tqdm

import pandas as pd

import mpbn, bonesis
from bonesis.asp_encoding import clingo_encode

import bonesistools as bt

from utils import get_cfg

bonesis.settings["quiet"] = True

DISABLE_TQDM = os.getenv("TQDM_DISABLE", "0") == "1"
TQDM_TO_TTY = os.getenv("TQDM_TO_TTY", "0") == "1"

class ptqdm(tqdm):
    def __init__(self, *args, **kwargs):
        if TQDM_TO_TTY:
            kwargs.setdefault("file", open("/dev/tty", "w"))
        else:
            kwargs.setdefault("file", sys.stdout)

        kwargs.setdefault("leave", False)
        kwargs.setdefault("disable", DISABLE_TQDM)
        super().__init__(*args, **kwargs)

def write_bn(
    bn: mpbn.MPBooleanNetwork,
    bnet: Path,
    noi: Optional[Path] = None,
    dot: Optional[Path] = None,
    neato: Optional[Path] = None,
    circo: Optional[Path] = None,
    fdp: Optional[Path] = None,
    sfdp: Optional[Path] = None,
    remove_single_nodes: bool = False
):
    bn = bn.copy()
    bn.save(bnet)
    if noi is not None:
        noi_set = set(bn) - set(bn.constants())
        with open(noi, "w") as fp:
            fp.write("".join([f"{n}\n" for n in noi_set]))
    if dot is not None or neato is not None or circo is not None or fdp is not None or sfdp is not None:
        if remove_single_nodes is True:
            nodes_to_remove = []
            for node in bn:
                if bn[node] in [bn.ba.FALSE, bn.ba.TRUE]:
                    nodes_to_remove.append(node)
            for node in nodes_to_remove:
                del bn[node]
        _dot = bt.bpy.bn_to_pydot(bn)
        if dot is not None:
            _dot.write(dot, prog="dot", format="raw")
        if neato is not None:
            _dot.write(neato, prog="neato", format="raw")
        if circo is not None:
            _dot.write(circo, prog="circo", format="raw")
        if fdp is not None:
            _dot.write(fdp, prog="fdp", format="raw")
        if sfdp is not None:
            _dot.write(sfdp, prog="sfdp", format="raw")

def dict_to_str(d: dict) -> str:
    s = ""; add = ""
    for k, v in d.items():
        s += f"{add}{k}->{v}"; add = ", "
        return s

parser_description = """
Infer Most Permissive Boolean Networks (MPBN) using bonesis paradigm. \
Four actions are proposed:
    - filter-nodes: component selection maximizing variable number while constraining Boolean networks to be compatible with the observations
    - filter-consts: component selection deleting strong constants while constraining Boolean networks to be compatible with the observations
    - min: solution of BN minimizing the edge number
    - sub: diverse solutions of sparsest BNs
See Chevalier et al. (2024) <https://hal.science/hal-04629083/document>.
"""

parser = argparse.ArgumentParser(
    prog="inference",
    description=parser_description,
    usage="python inference.py [filter-nodes | filter-consts | one | min | sub] <FILE> <FILE> [<args>]",
    formatter_class=argparse.RawTextHelpFormatter
)

parser.add_argument(
    "action",
    choices=["filter-nodes", "filter-consts", "one", "min", "sub"],
    metavar="[filter-nodes | filter-consts | one | min | sub]"
)

parser.add_argument(
    "spec",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file containing model specifications in Bonesis langage (format: txt)"
)

parser.add_argument(
    "mstates",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing partially binarized metastates (format: csv)"
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
    "--mandatory-genes",
    dest="mandatory_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="input file storing mandatory genes, being forced to appear (format: json or txt)"
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
    help="output file storing bonesis solution (format: txt for 'filter-nodes'/'filter-consts', bnet for 'one' or 'min' and path for 'sub')"
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
    "--organism",
    dest="organism",
    action=cli.Store_organism,
    default="mouse",
    required=False
)

parser.add_argument(
    "--bonesis-mode",
    dest="bonesis_mode",
    action=cli.Bonesis_mode
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
    "--minimize-self-loops",
    dest="minimize_self_loops",
    required=False,
    action="store_true",
    help="minimize the number of self loops"
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
    "--limit",
    dest="limit",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of diverse subset minimal solutions. If not specified, enumerate all subset minimal solutions without diversity (default: None)"
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
    "--dot",
    dest="dot",
    required=False,
    action="store_true",
    help="save BN associated-influence graph with dot program"
)

parser.add_argument(
    "--neato",
    dest="neato",
    required=False,
    action="store_true",
    help="save BN associated-influence graph with neato program"
)

parser.add_argument(
    "--circo",
    dest="circo",
    required=False,
    action="store_true",
    help="save BN associated-influence graph with circo program"
)

parser.add_argument(
    "--fdp",
    dest="fdp",
    required=False,
    action="store_true",
    help="save BN associated-influence graph with fdp program"
)

parser.add_argument(
    "--sfdp",
    dest="sfdp",
    required=False,
    action="store_true",
    help="save BN associated-influence graph with sfdp program"
)

parser.add_argument(
    "--remove-single-nodes",
    dest="remove_single_nodes",
    required=False,
    action="store_true",
    help="remove nodes without interaction with another node when printing influence graph"
)

parser.add_argument(
    "--jobs",
    dest="jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of allocated processors (used only when searching for diverse solutions of Boolean network)"
)

args = parser.parse_args()

if args.bonesis_mode != "hard":
    std.print_warning(f"some constraints are removed (bonesis mode: {args.bonesis_mode})")

bonesis.settings["parallel"] = args.jobs

genesyn = bt.dbs.ncbi.GeneSynonyms(organism=args.organism)

std.print_task(f"loading partially binarized metastates {str(args.mstates)}")

mstates_df = pd.read_csv(args.mstates, index_col=0, sep=args.sep).fillna(float("nan"))

mstates_cfg = get_cfg(
    mstates_df,
    axis="index"
)

std.print_task("initializing bonesis settings")

pkn_options = {
    "canonic": False if args.action.startswith("filter") else True,
    "maxclause": args.max_clause,
}
if args.action == "filter-nodes":
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

bo = bonesis.BoNesis(pkn, mstates_cfg)

with open(args.spec, "r") as file:
    for line in file:
        exec(line.rstrip('\n'))

if args.bonesis_mode == "soft":
    new_constraints = True
    idx = []
    for i, bo_property in enumerate(bo.manager.properties):
        str_property = bo_property[0]
        if str_property in ["final_nonreach", "nonreach", "all_fixpoints", "allreach"]:
            idx.append(i)
    bo.manager.properties = [bo.manager.properties.copy()[i] for i in range(len(bo.manager.properties)) if i not in idx]
elif args.bonesis_mode == "relaxed":
    new_constraints = False
    idx = []
    for i, bo_property in enumerate(bo.manager.properties):
        str_property = bo_property[0]
        if str_property in ["all_fixpoints", "allreach"]:
            idx.append(i)
        if str_property in ["final_nonreach", "nonreach"]:
            new_constraints = True
    bo.manager.properties = [bo.manager.properties.copy()[i] for i in range(len(bo.manager.properties)) if i not in idx]
elif args.bonesis_mode == "hard":
    new_constraints = False
    for bo_property in bo.manager.properties:
        str_property = bo_property[0]
        if str_property in ["all_fixpoints", "allreach"]:
            new_constraints = True

if args.action == "filter-nodes":

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

    if new_constraints == False:
        std.print_debug("No new constraints added, stopping.", flush=True)
        with open(args.solution, "w") as file:
            for node in bo.domain.nodes:
                file.write(f"{node}\n")
        sys.exit(0)

    std.print_warning("this may take some time.", flush=True)
    solution = next(iter(view))

    with open(args.solution, "w") as file:
        for node in solution:
            file.write(f"{node}\n")
    
    nodes_in_data = set()
    for bin_nodes in bo.data.values():
        nodes_in_data.update(bin_nodes.keys())
    nodes_in_domain = set(bo.domain.nodes)

    if TQDM_TO_TTY:
        with open("/dev/tty", "w") as tty:
            print("", file=tty, flush=True)
    std.print_result(f"node number: [data: {len(nodes_in_data)}, domain: {len(nodes_in_domain)}, solution: {len(solution)}]", flush=True)
    std.print_result(f"node number: [kept in data: {len(nodes_in_data & solution)}, removed in data: {len(nodes_in_data - solution)}]", flush=True)
    std.print_result(f"node number: [kept in domain: {len(nodes_in_domain & solution)}, removed in domain: {len(nodes_in_domain - solution)}]", flush=True)

elif args.action == "filter-consts":

    std.print_task("filtering components by deleting strong constants while constraining Boolean networks to be compatible with the observations")
    
    bo.maximize_strong_constants()
    if args.minimize_self_loops:
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

    if TQDM_TO_TTY:
        with open("/dev/tty", "w") as tty:
            print("", file=tty, flush=True)
    std.print_result(f"node number: [data: {len(nodes_in_data)}, domain: {len(nodes_in_domain)}, solution: {len(solution)}]")
    std.print_result(f"node number: [kept in data: {len(nodes_in_data & solution)}, removed in data: {len(nodes_in_data - solution)}]")
    std.print_result(f"node number: [kept in domain: {len(nodes_in_domain & solution)}, removed in domain: {len(nodes_in_domain - solution)}]")

elif args.action == "min":

    std.print_task("computing solution of Boolean network minimizing the edge number")

    bo.custom("edge(A,B) :- clause(B,_,A,_). #minimize { 1@1,A,B: edge(A,B) }.")
    bo.custom("#maximize { 1@10,N: constant(N) }.")

    if args.minimize_self_loops:
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

    name_mapping = dict()
    bn = solution[1]
    for component in bn:
        if component not in nodes:
            name_mapping[component] = re.sub("_", "-", component)
    if name_mapping:
        print(""); std.print_debug(f"renaming components: {dict_to_str(name_mapping)}")
        for k, v in name_mapping.items():
            bn.rename(k, v)

    write_bn(
        bn=bn,
        bnet=f"{args.solution}.bnet",
        noi=f"{args.solution}.noi.txt",
        **{f"{program}": f"{os.path.dirname(args.solution)}/graph.{program}" if eval(f"args.{program}") else None for program in ["dot", "neato", "circo", "fdp", "sfdp"]},
        remove_single_nodes = args.remove_single_nodes
    )
    pd.DataFrame(solution[2]).to_csv(f"{args.solution}.csv")

elif args.action == "sub":

    std.print_task("sampling diverse solutions of Boolean network")

    os.makedirs(f"{args.solution}", exist_ok=True)

    view = bonesis.DiverseBooleanNetworksView(
        bo,
        extra=("configurations"),
        limit=args.limit if args.limit is not None else 0,
        progress=ptqdm
    )
    view.standalone(output_filename=args.asp)

    debug=True
    bns = bt.bpy.BooleanNetworkEnsemble(components=nodes)
    std.print_warning("this may take some time.")
    for i, solution in enumerate(ptqdm(view)):
        bn = solution[1] if isinstance(view, bonesis.views.InfluenceGraphView) else solution[0]
        if debug:
            name_mapping = dict()
            for component in bn:
                if component not in bns.get_components():
                    name_mapping[component] = re.sub("_", "-", component)
            if name_mapping:
                tqdm.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - DEBUG - renaming components: {dict_to_str(name_mapping)}")
            debug = False
        if name_mapping:
            for k, v in name_mapping.items():
                bn.rename(k, v)
        bns.append(bn)
        os.makedirs(f"{args.solution}/{i}")
        write_bn(
            bn=bn,
            bnet=f"{args.solution}/{i}/model.bnet",
            noi=f"{args.solution}/{i}/.noi.txt",
            **{f"{program}": f"{args.solution}/{i}/graph.{program}" if eval(f"args.{program}") else None for program in ["dot", "neato", "circo", "fdp", "sfdp"]},
            remove_single_nodes = args.remove_single_nodes
        )
        if isinstance(view, bonesis.views.InfluenceGraphView):
            pd.DataFrame(solution[2]).to_csv(f"{args.solution}/{i}/mstates.csv")
        else:
            pd.DataFrame(solution[1]).to_csv(f"{args.solution}/{i}/mstates.csv")

    std.print_task("analysing ensemble of Boolean networks")

    influences = bns.get_influences()

    import graphviz

    function_number = {component: 0 for component in bns.get_components()}

    if args.remove_single_nodes:
        transcription_factors = bns.get_transcription_factors()
        single_nodes = set()
        for node in bns.get_components():
            if transcription_factors[node] == {} and influences[node] == {}:
                single_nodes.add(node)
        interest_nodes = set(bns.get_components()) - single_nodes
    else:
        interest_nodes = set(bns.get_components())

    clauses = bns.get_clauses()
    function_number = {component: len(set(clauses_per_component)) for component, clauses_per_component in clauses.items()}

    ig_ensemble = graphviz.Digraph(
        name="Interaction graph ensemble",
        comment="influence graph aggregation"
    )
    ig_ensemble.graph_attr["ratio"] = "0.8"
    ig_ensemble.graph_attr["overlap"] = "false"
    ig_ensemble.graph_attr["splines"] = "true"

    for component in interest_nodes:
    #    if node not in constantes:
        if function_number[component] == 1:
            ig_ensemble.node(component, label=f"{component}", fillcolor="darkgoldenrod2", style="rounded,filled,bold", shape="oval", fontcolor="black", fontname="arial bold", fontsize="50pt")
        elif function_number[component] ==2:
            ig_ensemble.node(component, label=f"{component}", fillcolor="lightgoldenrod1", style="rounded,filled", shape="oval", fontsize="50pt")
        elif function_number[component] == 3:
            ig_ensemble.node(component, label=f"{component}", fillcolor="cornsilk", style="rounded,filled", shape="oval", fontsize="50pt")
        elif function_number[component] < 10:
            ig_ensemble.node(component, label=f"{component}", fillcolor="white", style="rounded,filled", shape="oval", fontsize="50pt")
        else:
            ig_ensemble.node(component, label=f"{component}", fillcolor="white", style="rounded,filled,dotted", shape="oval", fontsize="50pt")
    
    def get_intensity(occurrences, min_intensity: int = 1, max_intensity: int = 10, differentiel_with_max: int = 2):
        
        occurrences = sorted(occurrences)
        inf = occurrences[0]; sup = occurrences[-1]
        differentiel = max_intensity - min_intensity - differentiel_with_max
        intensity = {}

        for occurrence in occurrences:
            intensity[occurrence] = str(round(((occurrence-inf)/(sup-inf)) * differentiel) + inf)
        intensity[occurrences[-1]] = str(max_intensity)

        return intensity

    occurrences_list = set()
    for target, sources in influences.items():
        for source, infl in sources.items():
            occurrences_list.add(*set(infl.values()))
    
    intensity = get_intensity(occurrences_list)

    for source, targets in influences.items():
        for target, infl in targets.items():
            for sign, occurrence in infl.items():
                if sign is True:
                    ig_ensemble.edge(source, target, label=f"{occurrence}", penwidth=intensity[occurrence], color="darkgreen", fontcolor="darkgreen", fontname="arial bold", fontsize="30pt", arrowsize="2")
                else:
                    ig_ensemble.edge(source, target, label=f"{occurrence}", penwidth=intensity[occurrence], color="darkred", fontcolor="darkred", fontname="arial bold", fontsize="30pt", arrowsize="2")

    for program in ["dot", "neato", "circo", "fdp", "sfdp"]:
        if eval(f"args.{program}"):
            ig_ensemble.render(
                filename=f"_graph_summary.{program}",
                directory=f"{args.solution}",
                view=False,
                format="plain",
                engine=program
            )

    ig_ensemble.render(
        filename=f"_graph_summary.dot",
        directory=f"{args.solution}",
        view=False,
        format="pdf",
        engine="dot"
    )
