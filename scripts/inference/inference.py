#!/usr/bin/env python

from typing import Any, Optional, Mapping, Iterable, Sequence
from collections import defaultdict

import sys
import os, std
import argparse, cli
import json
from pathlib import Path

from tqdm import tqdm

import pandas as pd

import bonesis
from bonesis.asp_encoding import clingo_encode

import bonesistools as bt

from utils import get_cfg

bonesis.settings["quiet"] = True

DISABLE_TQDM = os.getenv("TQDM_DISABLE", "0") == "1"
TQDM_TO_TTY = os.getenv("TQDM_TO_TTY", "0") == "1"


class ptqdm(tqdm):
    def __init__(self, *args, **kwargs):

        kwargs.setdefault("leave", True)

        if TQDM_TO_TTY:
            kwargs.setdefault("file", open("/dev/tty", "w"))
        else:
            kwargs.setdefault("file", sys.stdout)

        kwargs.setdefault("disable", DISABLE_TQDM)
        super().__init__(*args, **kwargs)


def get_configuration_predicates(bo) -> dict:
    """
    Retrieve the semantic predicate associated with each BoNesis configuration.

    Parameters
    ----------
    bo: bonesis.BoNesis
        BoNesis object storing logical properties and configurations.

    Returns
    -------
    dict
        Mapping from BoNesis configuration keys to their associated semantic
        predicates.
    """

    predicates = {}

    for predicate, args, _ in bo.manager.properties:
        if predicate == "cfg":
            key = args[0]
            predicates.setdefault(key, "configuration")

        elif predicate in {"trapspace", "fixpoint"}:
            managed = args[0]
            predicates[managed.name] = predicate

    return predicates


def write_noi(bn, outfile):
    """
    Write non-constant Boolean network components to a text file.

    Each line of the output file contains the name of a non-constant
    component of the Boolean network.

    Parameters
    ----------
    bn: mpbn.MPBooleanNetwork
        Boolean network.
    outfile: str | Path
        Output text file.
    """
    noi_set = set(bn) - set(bn.constants())

    with open(outfile, "w") as fp:
        fp.write("".join(f"{node}\n" for node in noi_set))


def write_influence_graph(
    bn,
    outdir,
    programs=("dot",),
    remove_isolated_nodes=False,
):
    """
    Write the Boolean network associated influence graph using Graphviz.

    Parameters
    ----------
    bn: mpbn.MPBooleanNetwork
        Boolean network.
    outdir: str | Path
        Output directory.
    programs: sequence of str, default=("dot",)
        Graphviz layout programs used to generate the graph.
        Examples include "dot", "neato", "circo", "fdp" and "sfdp".
    remove_isolated_nodes: bool, default=False
        Whether to remove constant components before graph generation.
    """

    bn = bt.bpy.bn.BooleanNetwork(bn.copy())

    if remove_isolated_nodes:
        for node in list(bn):
            if bn[node] in [bn.ba.FALSE, bn.ba.TRUE]:
                del bn[node]

    graph = bn.to_pydot()

    for program in programs:
        graph.write(
            outdir / f"ig.{program}",
            prog=program,
            format="raw",
        )

    return None


def write_configurations(cfgs, outfile):
    """
    Write Boolean configurations using the format inferred from the output
    file extension.

    Supported output formats are:
    - .cfg : sparse logical configuration format
    - .csv : tabular representation
    - .json : structured JSON representation

    Parameters
    ----------
    cfgs: Mapping
        Mapping of configuration names to component-state mappings.
    outfile: str | Path
        Output configuration file. The export format is inferred from the
        file extension.

    Raises
    ------
    ValueError
        If the output file extension is not supported.
    """

    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)

    suffix = outfile.suffix

    if suffix == ".cfg":

        with open(outfile, "w") as f:
            for cfg_name, cfg in cfgs.items():
                f.write(f"[{cfg_name}]\n")

                for key, value in cfg.items():
                    if value not in [0, 1, False, True]:
                        continue

                    f.write(f"{key}={int(value)}\n")

                f.write("\n")

    elif suffix == ".csv":

        csv_cfgs = {
            cfg_name: {k: (None if v == "*" else v) for k, v in cfg.items()}
            for cfg_name, cfg in cfgs.items()
        }

        df = pd.DataFrame(csv_cfgs).astype("Int8")
        df.to_csv(outfile)

    elif suffix == ".json":

        json_cfgs = {
            cfg_name: {k: (None if v == "*" else v) for k, v in cfg.items()}
            for cfg_name, cfg in cfgs.items()
        }

        with open(outfile, "w") as f:
            json.dump(json_cfgs, f, indent=4)

    else:
        raise ValueError(
            f"unsupported output format: '{suffix}' "
            "(supported formats: .cfg, .csv, .json)"
        )


def write_solution(
    bn,
    configurations: Mapping,
    outdir,
    config_formats: Sequence[str] = ("cfg",),
    graph_formats: Sequence[str] = (),
    remove_isolated_nodes: bool = False,
) -> None:
    """
    Write a Boolean network solution and associated outputs.

    Parameters
    ----------
    bn: mpbn.MPBooleanNetwork
        Boolean network solution.
    configurations: Mapping
        Mapping of configuration names to component-state mappings.
    outdir: str | Path
        Output directory where solution files are written.
    config_formats: sequence of str, default=("cfg",)
        Configuration output formats. Supported formats are "cfg", "csv"
        and "json".
    graph_formats: sequence of str, default=()
        Graphviz layout programs used to export the associated influence graph.
        Examples include "dot", "neato", "circo", "fdp" and "sfdp".
    remove_isolated_nodes: bool, default=False
        Whether to remove constant components from exported influence graphs.
    """

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    bn.save(outdir / "model.bnet")

    write_noi(
        bn,
        outdir / "noi.txt",
    )

    for fmt in config_formats:
        write_configurations(
            configurations,
            outdir / f"state.{fmt}",
        )

    if graph_formats:
        write_influence_graph(
            bn,
            outdir,
            programs=graph_formats,
            remove_isolated_nodes=remove_isolated_nodes,
        )

    return None

def run_bn_view(
    view: Any,
    components: Iterable[str],
    outdir: str | Path,
    config_formats: Sequence[str],
    graph_formats: Sequence[str],
    normalized_to_original_gene_names: Optional[Mapping[str, str]] = None,
    trapspace_configurations: Optional[Sequence[Any]] = None,
    rename_cfgs: Optional[Mapping[Any, Any]] = None,
    remove_isolated_nodes: bool = False,
) -> bt.bpy.bn.BooleanNetworkEnsemble:
    """
    Enumerate, post-process and export Boolean network solutions produced by a
    BoNesis view.

    The function supports BoNesis views returning either Boolean networks
    directly or influence graphs with associated Boolean networks. For each
    solution, it restores original gene names when needed, appends the Boolean
    network to an ensemble, converts trapspace-associated configurations into
    principal trap spaces, simplifies tuple-based configuration names, and writes
    the solution to a numbered output directory.

    Parameters
    ----------
    view:
        BoNesis view enumerating Boolean network solutions.
    components:
        Components used to initialize the Boolean network ensemble.
    outdir:
        Root output directory where numbered solution folders are written.
    config_formats:
        Configuration output formats.
    graph_formats:
        Graphviz layout programs used for influence graph export.
    normalized_to_original_gene_names:
        Mapping from BoNesis-compatible gene names to original gene names.
    trapspace_configurations:
        Names of configurations that should be converted to principal trap
        spaces.
    rename_cfgs:
        Mapping from original configuration names to simplified names.
    remove_isolated_nodes:
        Whether isolated nodes should be removed from exported influence graphs.

    Returns
    -------
    bt.bpy.bn.BooleanNetworkEnsemble
        Ensemble containing the exported Boolean network solutions.

    Raises
    ------
    TypeError
        If the view type is not supported.
    """

    outdir = Path(outdir)
    normalized_to_original_gene_names = normalized_to_original_gene_names or {}
    trapspace_configurations = trapspace_configurations or []
    rename_cfgs = rename_cfgs or {}

    ensemble = bt.bpy.bn.BooleanNetworkEnsemble(components=components)

    for i, solution in enumerate(view):

        if isinstance(view, bonesis.DiverseBooleanNetworksView):
            bn, configs = solution

        elif isinstance(view, bonesis.InfluenceGraphView):
            _, bn, configs = solution

        else:
            raise TypeError(f"unsupported BoNesis view type: {type(view).__name__}")

        for old, new in normalized_to_original_gene_names.items():
            bn.rename(old, new)

        ensemble.append(bn)

        for cfg_name in trapspace_configurations:
            cfg_state = configs[cfg_name]
            ts = bn.principal_trapspace(cfg_state)
            configs[cfg_name] = {k: v for k, v in ts.items() if v != "*"}

        for old, new in rename_cfgs.items():
            configs[new] = configs.pop(old)

        write_solution(
            bn=bn,
            configurations=configs,
            outdir=outdir / str(i),
            config_formats=config_formats,
            graph_formats=graph_formats,
            remove_isolated_nodes=remove_isolated_nodes,
        )

    return ensemble

parser_description = """
Infer Most Permissive Boolean Networks (MPBNs) using the BoNesis paradigm.

Five actions are proposed:
    - filter-nodes:
        component selection maximizing variable number while constraining
        Boolean networks to satisfy the observations
    - filter-consts:
        component selection removing strong constants while constraining
        Boolean networks to satisfy the observations
    - min:
        inference of a Boolean network minimizing the number of interactions
    - submin:
        enumeration of Boolean networks associated with subset-minimal
        influence graphs
    - diverse:
        sampling of diverse sparsest Boolean network solutions

See Chevalier et al. (2024):
https://hal.science/hal-04629083/document
"""

parser = argparse.ArgumentParser(
    prog="inference",
    description=parser_description,
    usage="python inference.py [filter-nodes | filter-consts | min | submin | diverse] <FILE> <FILE> [<args>]",
    formatter_class=argparse.RawTextHelpFormatter,
)

parser.add_argument(
    "action",
    choices=["filter-nodes", "filter-consts", "min", "submin", "diverse"],
    metavar="[filter-nodes | filter-consts | min | submin | diverse]",
)

parser.add_argument(
    "spec",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file containing model specifications in Bonesis langage (format: txt)",
)

parser.add_argument(
    "mstates",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing partially binarized metastates (format: csv)",
)

parser.add_argument(
    "--important-genes",
    dest="important_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="input file storing important genes, being prioritize to appear (format: json or txt)",
)

parser.add_argument(
    "--mandatory-genes",
    dest="mandatory_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="input file storing mandatory genes, being forced to appear (format: json or txt)",
)

parser.add_argument(
    "--filter-grn",
    dest="filter_grn",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="file with one node per line (txt format)",
)

parser.add_argument(
    "--asp",
    dest="asp",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="output file storing asp command (format: sh)",
)

parser.add_argument(
    "--solution",
    dest="solution",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE | PATH",
    help="output file storing bonesis solution (format: txt for 'filter-nodes'/'filter-consts', bnet for 'one' or 'min' and path for 'sub')",
)

parser.add_argument(
    "--config-formats",
    dest="config_formats",
    nargs="+",
    choices=["cfg", "csv", "json"],
    default=["csv"],
    metavar="[csv | cfg | json]",
    help=("output formats used for exporting Boolean configurations " "(default: csv)"),
)

parser.add_argument(
    "--domain",
    dest="domain",
    action=cli.Bonesis_domain,
    required=False,
    default="collectri",
)

parser.add_argument(
    "--organism",
    dest="organism",
    action=cli.Store_organism,
    default="mouse",
    required=False,
)

parser.add_argument("--bonesis-mode", dest="bonesis_mode", action=cli.Bonesis_mode)

parser.add_argument(
    "--max-clause",
    dest="max_clause",
    type=int,
    required=False,
    default=8,
    metavar="INT",
    help="maximum number of literals/atoms in each propositional formula (default: 8)",
)

parser.add_argument(
    "--minimize-self-loops",
    dest="minimize_self_loops",
    required=False,
    action="store_true",
    help="minimize the number of self loops",
)

parser.add_argument(
    "--clingo-opt-mode",
    dest="clingo_opt_mode",
    action=cli.Clingo_opt_mode,
    required=False,
    default="optN",
)

parser.add_argument(
    "--clingo-opt-strategy",
    dest="clingo_opt_strategy",
    action=cli.Clingo_opt_strategy,
    required=False,
)

parser.add_argument(
    "--limit",
    dest="limit",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of diverse subset minimal solutions. If not specified, enumerate all subset minimal solutions without diversity (default: None)",
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
    "--graph-formats",
    dest="graph_formats",
    nargs="+",
    choices=["dot", "neato", "circo", "fdp", "sfdp"],
    default=[],
    metavar="[dot | neato | circo | fdp | sfdp]",
    help=(
        "graphviz layout programs used for exporting Boolean network "
        "associated influence graphs"
    ),
)

parser.add_argument(
    "--remove-isolated-nodes",
    dest="remove_isolated_nodes",
    required=False,
    action="store_true",
    help="remove nodes without interaction with another node when printing influence graph",
)

parser.add_argument(
    "--jobs",
    dest="jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of allocated processors (used only when searching for diverse solutions of Boolean network)",
)

args = parser.parse_args()

if args.bonesis_mode != "hard":
    std.print_warning(
        f"some constraints are removed (bonesis mode: {args.bonesis_mode})"
    )

bonesis.settings["parallel"] = args.jobs

genesyn = bt.dbs.ncbi.GeneSynonyms(organism=args.organism)

std.print_task(f"loading partially binarized metastates from {str(args.mstates)}")

mstates_df = pd.read_csv(args.mstates, index_col=0, sep=args.sep).fillna(float("nan"))

mstates_cfg = get_cfg(mstates_df, axis="index")

std.print_task("initializing BoNesis inference settings")

pkn_options = {
    "canonic": False if args.action.startswith("filter") else True,
    "maxclause": args.max_clause,
}
if args.action == "filter-nodes":
    pkn_options["allow_skipping_nodes"] = True

if args.domain == "collectri":
    grn = bt.dbs.omnipath.load_collectri_grn(
        organism=args.organism,
        genesyn=genesyn,
    )
elif args.domain == "dorothea":
    grn = bt.dbs.omnipath.load_dorothea_grn(
        organism=args.organism,
        genesyn=genesyn,
    )
else:
    grn = bt.grn.read_interaction_graph(
        infile=args.domain,
        genesyn=genesyn,
    )

if args.filter_grn:
    with open(args.filter_grn) as fp:
        nodes = [line.strip() for line in fp.readlines()]
    grn = grn.subgraph(nodes)
    del nodes

pkn = bonesis.domains.InfluenceGraph(grn, **pkn_options)

bo = bonesis.BoNesis(pkn, mstates_cfg)

with open(args.spec, "r") as file:
    for line in file:
        exec(line.rstrip("\n"))

if args.bonesis_mode == "soft":
    new_constraints = True
    idx = []
    for i, bo_property in enumerate(bo.manager.properties):
        str_property = bo_property[0]
        if str_property in ["final_nonreach", "nonreach", "all_fixpoints", "allreach"]:
            idx.append(i)
    bo.manager.properties = [
        bo.manager.properties.copy()[i]
        for i in range(len(bo.manager.properties))
        if i not in idx
    ]
elif args.bonesis_mode == "relaxed":
    new_constraints = False
    idx = []
    for i, bo_property in enumerate(bo.manager.properties):
        str_property = bo_property[0]
        if str_property in ["all_fixpoints", "allreach"]:
            idx.append(i)
        if str_property in ["final_nonreach", "nonreach"]:
            new_constraints = True
    bo.manager.properties = [
        bo.manager.properties.copy()[i]
        for i in range(len(bo.manager.properties))
        if i not in idx
    ]
elif args.bonesis_mode == "hard":
    new_constraints = False
    for bo_property in bo.manager.properties:
        str_property = bo_property[0]
        if str_property in ["all_fixpoints", "allreach"]:
            new_constraints = True

if args.action == "filter-nodes":

    std.print_task(
        "filtering components by maximizing variable number while constraining Boolean networks to be compatible with the observations"
    )

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
        progress=ptqdm,
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
    std.print_result(
        f"node number: [data: {len(nodes_in_data)}, domain: {len(nodes_in_domain)}, solution: {len(solution)}]",
        flush=True,
    )
    std.print_result(
        f"node number: [kept in data: {len(nodes_in_data & solution)}, removed in data: {len(nodes_in_data - solution)}]",
        flush=True,
    )
    std.print_result(
        f"node number: [kept in domain: {len(nodes_in_domain & solution)}, removed in domain: {len(nodes_in_domain - solution)}]",
        flush=True,
    )

elif args.action == "filter-consts":

    std.print_task(
        "filtering components by deleting strong constants while constraining Boolean networks to be compatible with the observations"
    )

    bo.maximize_strong_constants()
    if args.minimize_self_loops:
        bo.custom("edge(A,A) :- clause(A,_,A,_). #minimize { 1@10000,A: edge(A,A) }.")

    view = bonesis.NonStrongConstantNodesView(
        bo,
        mode=args.clingo_opt_mode,
        clingo_opt_strategy="usc",
        clingo_options=["--opt-usc-shrink=inv"],
        progress=ptqdm,
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
    std.print_result(
        f"node number: [data: {len(nodes_in_data)}, domain: {len(nodes_in_domain)}, solution: {len(solution)}]"
    )
    std.print_result(
        f"node number: [kept in data: {len(nodes_in_data & solution)}, removed in data: {len(nodes_in_data - solution)}]"
    )
    std.print_result(
        f"node number: [kept in domain: {len(nodes_in_domain & solution)}, removed in domain: {len(nodes_in_domain - solution)}]"
    )

else:

    normalized_to_original_gene_names = {
        gene.replace("-", "_"): gene for gene in bo.domain.nodes if "-" in gene
    }
    if normalized_to_original_gene_names:
        std.print_debug(
            "unsupported '-' characters detected in gene names; "
            "the following gene names will be restored after BoNesis inference: "
            f"{', '.join(f'{k} -> {v}' for k, v in normalized_to_original_gene_names.items())}"
        )

    config_predicates = get_configuration_predicates(bo)
    predicate_configs = defaultdict(list)
    for config, predicate in config_predicates.items():
        predicate_configs[predicate].append(config)
    if "trapspace" in predicate_configs:
        std.print_debug(
            "trapspace predicates detected; "
            "principal trap spaces will be computed for: "
            f"{', '.join(map(str, predicate_configs['trapspace']))}"
        )

    rename_cfgs = {}
    for predicate, cfg_names in predicate_configs.items():
        grouped = defaultdict(list)
        for cfg_name in cfg_names:
            if isinstance(cfg_name, tuple):
                grouped[cfg_name[0]].append(cfg_name)
        for name, tuples in grouped.items():
            if len(tuples) == 1 and tuples[0][1] == 0:
                rename_cfgs[tuples[0]] = name
    if rename_cfgs:
        std.print_debug(
            "the following tuple-based configuration names will be simplified: "
            f"{', '.join(f'{k} -> {v}' for k, v in rename_cfgs.items())}"
        )

    if args.action == "min":

        std.print_task(
            "computing solution of Boolean network minimizing the edge number"
        )

        bo.custom("edge(A,B) :- clause(B,_,A,_). #minimize { 1@1,A,B: edge(A,B) }.")
        bo.custom("#maximize { 1@10,N: constant(N) }.")

        if args.minimize_self_loops:
            bo.custom("#minimize { 1@100,A: edge(A,A) }.")

        view = bonesis.InfluenceGraphView(
            bo,
            mode=args.clingo_opt_mode,
            clingo_opt_strategy="usc",
            extra=("boolean-network", "configurations"),
            progress=ptqdm,
        )
        view.standalone(output_filename=args.asp)

        std.print_warning("this may take some time.")
        solution = next(iter(view))

        _, bn, configs = solution

        if normalized_to_original_gene_names:
            for k, v in normalized_to_original_gene_names.items():
                bn.rename(k, v)

        if "trapspace" in predicate_configs:
            for cfg_name in predicate_configs["trapspace"]:
                cfg_state = configs[cfg_name]
                ts = bn.principal_trapspace(cfg_state)
                ts = {k: v for k, v in ts.items() if v != "*"}
                configs[cfg_name] = ts

        for _old, _new in rename_cfgs.items():
            configs[_new] = configs.pop(_old)

        write_solution(
            bn=bn,
            configurations=configs,
            outdir=args.solution,
            config_formats=args.config_formats,
            graph_formats=args.graph_formats,
            remove_isolated_nodes=args.remove_isolated_nodes,
        )

    elif args.action == "submin":

        if args.limit not in [None, 0]:
            std.print_task(
                f"enumerating {args.limit} subset-minimal Boolean network solutions"
            )
        else:
            std.print_task("enumerating subset-minimal Boolean network solutions")

        std.print_warning("this may take some time.")

        view = bonesis.InfluenceGraphView(
            bo,
            solutions="subset-minimal",
            extra=("boolean-network", "configurations"),
            limit=args.limit if args.limit is not None else 0,
            progress=ptqdm,
        )
        view.standalone(output_filename=args.asp)

        bns = run_bn_view(
            view=view,
            components=bo.domain.nodes,
            outdir=args.solution,
            config_formats=args.config_formats,
            graph_formats=args.graph_formats,
            normalized_to_original_gene_names=normalized_to_original_gene_names,
            trapspace_configurations=predicate_configs.get("trapspace", []),
            rename_cfgs=rename_cfgs,
            remove_isolated_nodes=args.remove_isolated_nodes,
        )

    elif args.action == "diverse":

        if args.limit not in [None, 0]:
            std.print_task(f"sampling {args.limit} sparsest Boolean network solutions")
        else:
            std.print_task("sampling sparsest Boolean network solutions")

        std.print_warning("this may take some time.")

        view = bonesis.DiverseBooleanNetworksView(
            bo,
            extra=("configurations",),
            limit=args.limit if args.limit is not None else 0,
            progress=ptqdm,
        )
        view.standalone(output_filename=args.asp)

        bns = run_bn_view(
            view=view,
            components=bo.domain.nodes,
            outdir=args.solution,
            config_formats=args.config_formats,
            graph_formats=args.graph_formats,
            normalized_to_original_gene_names=normalized_to_original_gene_names,
            trapspace_configurations=predicate_configs.get("trapspace", []),
            rename_cfgs=rename_cfgs,
            remove_isolated_nodes=args.remove_isolated_nodes,
        )
    
#        std.print_task("analysing ensemble of Boolean networks")
#
#        influences = bns.get_influences()
#
#        import graphviz
#
#        function_number = {component: 0 for component in bns.get_components()}
#
#        if args.remove_isolated_nodes:
#            transcription_factors = bns.get_transcription_factors()
#            single_nodes = set()
#            for node in bns.get_components():
#                if transcription_factors[node] == {} and influences[node] == {}:
#                    single_nodes.add(node)
#            interest_nodes = set(bns.get_components()) - single_nodes
#        else:
#            interest_nodes = set(bns.get_components())
#
#        clauses = bns.get_clauses()
#        function_number = {
#            component: len(set(clauses_per_component))
#            for component, clauses_per_component in clauses.items()
#        }
#
#        ig_ensemble = graphviz.Digraph(
#            name="Interaction graph ensemble", comment="influence graph aggregation"
#        )
#        ig_ensemble.graph_attr["ratio"] = "0.8"
#        ig_ensemble.graph_attr["overlap"] = "false"
#        ig_ensemble.graph_attr["splines"] = "true"
#
#        for component in interest_nodes:
#            #    if node not in constantes:
#            if function_number[component] == 1:
#                ig_ensemble.node(
#                    component,
#                    label=f"{component}",
#                    fillcolor="darkgoldenrod2",
#                    style="rounded,filled,bold",
#                    shape="oval",
#                    fontcolor="black",
#                    fontname="arial bold",
#                    fontsize="50pt",
#                )
#            elif function_number[component] == 2:
#                ig_ensemble.node(
#                    component,
#                    label=f"{component}",
#                    fillcolor="lightgoldenrod1",
#                    style="rounded,filled",
#                    shape="oval",
#                    fontsize="50pt",
#                )
#            elif function_number[component] == 3:
#                ig_ensemble.node(
#                    component,
#                    label=f"{component}",
#                    fillcolor="cornsilk",
#                    style="rounded,filled",
#                    shape="oval",
#                    fontsize="50pt",
#                )
#            elif function_number[component] < 10:
#                ig_ensemble.node(
#                    component,
#                    label=f"{component}",
#                    fillcolor="white",
#                    style="rounded,filled",
#                    shape="oval",
#                    fontsize="50pt",
#                )
#            else:
#                ig_ensemble.node(
#                    component,
#                    label=f"{component}",
#                    fillcolor="white",
#                    style="rounded,filled,dotted",
#                    shape="oval",
#                    fontsize="50pt",
#                )
#
#        def get_intensity(
#            occurrences,
#            min_intensity: int = 1,
#            max_intensity: int = 10,
#            differentiel_with_max: int = 2,
#        ):
#
#            occurrences = sorted(occurrences)
#            inf = occurrences[0]
#            sup = occurrences[-1]
#            differentiel = max_intensity - min_intensity - differentiel_with_max
#            intensity = {}
#
#            for occurrence in occurrences:
#                intensity[occurrence] = str(
#                    round(((occurrence - inf) / (sup - inf)) * differentiel) + inf
#                )
#            intensity[occurrences[-1]] = str(max_intensity)
#
#            return intensity
#
#        occurrences_list = set()
#        for target, sources in influences.items():
#            for source, infl in sources.items():
#                occurrences_list.add(*set(infl.values()))
#
#        intensity = get_intensity(occurrences_list)
#
#        for source, targets in influences.items():
#            for target, infl in targets.items():
#                for sign, occurrence in infl.items():
#                    if sign is True:
#                        ig_ensemble.edge(
#                            source,
#                            target,
#                            label=f"{occurrence}",
#                            penwidth=intensity[occurrence],
#                            color="darkgreen",
#                            fontcolor="darkgreen",
#                            fontname="arial bold",
#                            fontsize="30pt",
#                            arrowsize="2",
#                        )
#                    else:
#                        ig_ensemble.edge(
#                            source,
#                            target,
#                            label=f"{occurrence}",
#                            penwidth=intensity[occurrence],
#                            color="darkred",
#                            fontcolor="darkred",
#                            fontname="arial bold",
#                            fontsize="30pt",
#                            arrowsize="2",
#                        )
#
#        for program in args.graph_formats:
#            ig_ensemble.render(
#                filename=f"_graph_summary.{program}",
#                directory=f"{args.solution}",
#                view=False,
#                format="plain",
#                engine=program,
#            )
#
#        ig_ensemble.render(
#            filename=f"_graph_summary.dot",
#            directory=f"{args.solution}",
#            view=False,
#            format="pdf",
#            engine="dot",
#        )
#