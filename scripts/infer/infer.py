#!/usr/bin/env python

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

import bonesis
import bonesistools as bt
import pandas as pd
from mpbn import MPBooleanNetwork
from _witness import (
    apply_structural_witness_heuristics,
    canonicalize_structural_witness,
    read_structural_witness,
)
from utils import (
    add_bonesis_arguments,
    apply_bonesis_mode,
    close_progress,
    get_clingo_parallel_mode,
    get_node_sets,
    initialize_bonesis,
    next_solution,
    print_solver_options,
    print_node_reference,
    ptqdm,
)

from scbolt import cli, console
from scbolt.runtime import (
    SolverDeadline,
    SolverTimeout,
    exit_solver_timeout,
    iter_solutions,
    reset_solver_timeout_status,
)

bonesis.settings["quiet"] = True
script_name = Path(__file__).name

AGGREGATED_INFLUENCE_GRAPH_GRAPH_ATTR: Mapping[str, str] = {
    "ratio": "compress",
    "overlap": "prism",
    "sep": "+0",
    "esep": "+0",
    "K": "0.35",
    "ranksep": "0.6",
    "pack": "true",
    "rankdir": "TB",
    "splines": "curve",
}
AGGREGATED_INFLUENCE_GRAPH_BASE_OPTIONS: Mapping[str, Any] = {
    "edge_label": "frequency",
    "node_style": "stability",
    "edge_style": "frequency",
    "preserve_feedback": True,
    "include_selfloops": False,
    "min_frequency": 0,
    "program": "dot",
    "graph_attr": AGGREGATED_INFLUENCE_GRAPH_GRAPH_ATTR,
    "node_attr": {
        "fontsize": "20",
    },
    "edge_attr": {
        "fontsize": "20",
    },
}
AGGREGATED_INFLUENCE_GRAPH_OPTIONS: Mapping[str, Mapping[str, Any]] = {
    "aggregate.pdf": {
        **AGGREGATED_INFLUENCE_GRAPH_BASE_OPTIONS,
        "collapse": None,
        "drop_isolates": True,
    },
    "aggregate_with_isolates.pdf": {
        **AGGREGATED_INFLUENCE_GRAPH_BASE_OPTIONS,
        "collapse": None,
        "drop_isolates": False,
    },
    "function_families.pdf": {
        **AGGREGATED_INFLUENCE_GRAPH_BASE_OPTIONS,
        "collapse": "family",
        "drop_isolates": True,
    },
    "feedback_core.pdf": {
        **AGGREGATED_INFLUENCE_GRAPH_BASE_OPTIONS,
        "collapse": "feedback",
        "drop_isolates": True,
    },
}


def get_configuration_predicates(bo) -> dict:
    """Retrieve the semantic predicate associated with each configuration."""

    predicates = {}

    for predicate, args, _ in bo.manager.properties:
        if predicate == "cfg":
            key = args[0]
            predicates.setdefault(key, "configuration")
        elif predicate in {"trapspace", "fixpoint"}:
            managed = args[0]
            predicates[managed.name] = predicate

    return predicates


def get_subset_minimal_clingo_settings(jobs):
    """Return parallel Clingo settings for subset-minimal enumeration."""

    parallel_jobs, parallel_option = get_clingo_parallel_mode(jobs)

    if parallel_option:
        return {"parallel": None, "clingo_options": [parallel_option]}
    if parallel_jobs <= 1:
        return {}

    return {"parallel": min(parallel_jobs, 14)}


def write_noi(bn: MPBooleanNetwork, file):
    """Write non-constant Boolean network components to a text file."""

    noi_set = set(bn) - set(bn.constants())

    with open(file, "w") as stream:
        stream.write("".join(f"{node}\n" for node in noi_set))


def to_bonesistools_boolean_network(
    bn: MPBooleanNetwork,
) -> bt.logic.bn.BooleanNetwork:
    """Adapt MPBN only for bonesistools graph export APIs."""

    return bt.logic.bn.BooleanNetwork(bn.copy())


def write_influence_graph(
    bn: MPBooleanNetwork,
    outdir,
    programs=("dot",),
    remove_isolated_nodes=False,
):
    """Write the Boolean network influence graph using Graphviz."""

    graph_bn = to_bonesistools_boolean_network(bn)
    influence_graph = graph_bn.to_influence_graph()

    if remove_isolated_nodes:
        isolated_nodes = [
            node for node, degree in influence_graph.degree if degree == 0
        ]
        influence_graph.remove_nodes_from(isolated_nodes)

    graph = influence_graph.to_pydot()

    for program in programs:
        graph.write(
            outdir / f"ig.{program}",
            prog=program,
            format="raw",
        )


def write_configurations(cfgs, file):
    """Write Boolean configurations using the output extension as format."""

    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)

    suffix = file.suffix

    if suffix == ".cfg":
        with open(file, "w") as stream:
            for cfg_name, cfg in cfgs.items():
                stream.write(f"[{cfg_name}]\n")

                for key, value in cfg.items():
                    if value not in [0, 1, False, True]:
                        continue

                    stream.write(f"{key}={int(value)}\n")

                stream.write("\n")

    elif suffix == ".csv":
        csv_cfgs = {
            cfg_name: {k: (None if v == "*" else v) for k, v in cfg.items()}
            for cfg_name, cfg in cfgs.items()
        }

        dataframe = pd.DataFrame(csv_cfgs).astype("Int8")
        dataframe.to_csv(file)

    elif suffix == ".json":
        json_cfgs = {
            cfg_name: {k: (None if v == "*" else v) for k, v in cfg.items()}
            for cfg_name, cfg in cfgs.items()
        }

        with open(file, "w") as stream:
            json.dump(json_cfgs, stream, indent=4)

    else:
        raise ValueError(
            f"unsupported output format: '{suffix}' "
            "(supported formats: .cfg, .csv, .json)"
        )


def write_solution(
    bn: MPBooleanNetwork,
    configurations: Mapping,
    outdir,
    config_formats: Sequence[str] = ("cfg",),
    graph_formats: Sequence[str] = (),
    remove_isolated_nodes: bool = False,
) -> None:
    """Write a Boolean network solution and its associated outputs."""

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    bn.save(outdir / "model.bnet")
    write_noi(bn, outdir / "noi.txt")

    for fmt in config_formats:
        write_configurations(
            configurations,
            outdir / f"configs.{fmt}",
        )

    if graph_formats:
        write_influence_graph(
            bn,
            outdir,
            programs=graph_formats,
            remove_isolated_nodes=remove_isolated_nodes,
        )


def write_ensemble_influence_graphs(
    bns: Sequence[MPBooleanNetwork],
    components: Iterable[str],
    outdir: str | Path,
) -> None:
    """Write aggregated influence graphs for an inferred BN ensemble."""

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    ensemble = bt.logic.bn.BooleanNetworkEnsemble(components=components)
    for bn in bns:
        ensemble.append(to_bonesistools_boolean_network(bn))

    if not bns:
        raise RuntimeError("cannot export aggregated influence graphs: no BN solution")

    console.print_task(
        "generating aggregated influence graphs "
        f"(folder={console.format_path(outdir)})"
    )
    graph = ensemble.to_influence_graph()

    for filename, options in AGGREGATED_INFLUENCE_GRAPH_OPTIONS.items():
        outfile = outdir / filename
        graph.to_pydot(**options).write_pdf(str(outfile))


def run_bn_view(
    view: Any,
    outdir: str | Path,
    config_formats: Sequence[str],
    graph_formats: Sequence[str],
    normalized_to_original_gene_names: Optional[Mapping[str, str]] = None,
    trapspace_configurations: Optional[Sequence[Any]] = None,
    rename_cfgs: Optional[Mapping[Any, Any]] = None,
    remove_isolated_nodes: bool = False,
    deadline: Optional[SolverDeadline] = None,
) -> list[MPBooleanNetwork]:
    """Enumerate, post-process and export Boolean network view solutions."""

    outdir = Path(outdir)
    normalized_to_original_gene_names = normalized_to_original_gene_names or {}
    trapspace_configurations = trapspace_configurations or []
    rename_cfgs = rename_cfgs or {}

    bns = []

    solutions = iter_solutions(view, deadline)
    try:
        for i, solution in enumerate(solutions, start=1):
            if isinstance(view, bonesis.DiverseBooleanNetworksView):
                bn, configs = solution
            elif isinstance(view, bonesis.InfluenceGraphView):
                _, bn, configs = solution
            else:
                raise TypeError(f"unsupported BoNesis view type: {type(view).__name__}")

            for old, new in normalized_to_original_gene_names.items():
                bn.rename(old, new)

            bns.append(bn)

            # Keep bn-submin/bn-diverse configurations as returned by BoNesis.
            # for cfg_name in trapspace_configurations:
            #     cfg_state = configs[cfg_name]
            #     ts = bn.principal_trapspace(cfg_state)
            #     configs[cfg_name] = {k: v for k, v in ts.items() if v != "*"}

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
    finally:
        solutions.close()
        close_progress(view)

    return bns


parser_description = """Infer Most Permissive Boolean Networks using BoNesis.

Three actions are proposed:
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

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="infer",
        description=parser_description,
        usage=(f"python {script_name} [min | submin | diverse] " "<FILE> <FILE> [<args>]"),
        formatter_class=cli.HelpFormatter,
    )
    parser.add_argument(
        "action",
        choices=["min", "submin", "diverse"],
        metavar="[min | submin | diverse]",
        help="BoNesis inference action to run",
    )
    add_bonesis_arguments(parser)
    parser.add_argument(
        "--initial-witness",
        dest="initial_witness",
        type=lambda value: Path(value).resolve(),
        required=False,
        default=None,
        metavar="FILE",
        help=(
            "structural witness used as a soft warm start for subset-minimal "
            "enumeration"
        ),
    )
    parser.add_argument(
        "--config-formats",
        dest="config_formats",
        nargs="+",
        choices=["cfg", "csv", "json"],
        default=["csv"],
        metavar="[csv | cfg | json]",
        help="output formats used for exporting Boolean configurations (default: csv)",
    )
    parser.add_argument(
        "--limit",
        dest="limit",
        type=int,
        required=False,
        default=None,
        metavar="INT",
        help=(
            "number of diverse subset minimal solutions; if not specified, "
            "enumerate all subset minimal solutions (default: None)"
        ),
    )
    parser.add_argument(
        "--graph-formats",
        dest="graph_formats",
        nargs="+",
        choices=["dot", "neato", "circo", "fdp", "sfdp"],
        default=[],
        metavar="[dot | neato | circo | fdp | sfdp]",
        help=(
            "Graphviz layout programs used for exporting Boolean network "
            "associated influence graphs (default: none)"
        ),
    )
    parser.add_argument(
        "--remove-isolated-nodes",
        dest="remove_isolated_nodes",
        required=False,
        action="store_true",
        help=(
            "remove nodes without interaction with another node when printing "
            "influence graph"
        ),
    )

    args = parser.parse_args()
    reset_solver_timeout_status(args.timeout_status_file)

    bo, canonical, _ = initialize_bonesis(
        args,
        allow_skipping_nodes=False,
        default_canonical=True,
    )
    apply_bonesis_mode(bo, args.bonesis_mode)

    if args.initial_witness is not None:
        if args.action != "submin":
            parser.error("--initial-witness is only supported with action 'submin'")

        witness = read_structural_witness(args.initial_witness)
        if witness:
            witness = canonicalize_structural_witness(witness)
            apply_structural_witness_heuristics(bo, witness)
            console.print_info(
                "applying canonical structural warm start "
                f"(file={console.format_path(args.initial_witness)})"
            )
        elif not args.initial_witness.is_file():
            console.print_warning(
                "structural warm-start witness is unavailable "
                f"(file={console.format_path(args.initial_witness)})"
            )

    normalized_to_original_gene_names = {
        gene.replace("-", "_"): gene for gene in bo.domain.nodes if "-" in gene
    }
    if normalized_to_original_gene_names:
        console.print_debug(
            "restoring gene names "
            "(phase=post-inference, reason=unsupported '-' characters, "
            f"genes={console.format_mapping(normalized_to_original_gene_names)})"
        )

    config_predicates = get_configuration_predicates(bo)
    predicate_configs = defaultdict(list)
    for config, predicate in config_predicates.items():
        predicate_configs[predicate].append(config)
    if "trapspace" in predicate_configs:
        console.print_debug(
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
        renamed_configs = ", ".join(map(str, rename_cfgs))
        console.print_debug(
            "simplifying configuration names "
            f"(reason=tuple-based names, configurations={renamed_configs})"
        )

    if args.action == "min":
        console.print_task("computing Boolean network solution (objective=minimize edges)")

        bo.custom("edge(A,B) :- clause(B,_,A,_). #minimize { 1@1,A,B: edge(A,B) }.")
        bo.custom("#maximize { 1@10,N: constant(N) }.")

        if args.minimize_self_loops:
            bo.custom("#minimize { 1@100,A: edge(A,A) }.")

        clingo_strategy = "usc"
        view = bonesis.InfluenceGraphView(
            bo,
            mode=args.clingo_mode,
            clingo_opt_strategy=clingo_strategy,
            extra=("boolean-network", "configurations"),
            progress=ptqdm,
        )
        view.standalone(output_filename=args.asp)

        print_node_reference(*get_node_sets(bo))
        print_solver_options(
            args.clingo_mode,
            clingo_strategy,
            args.max_clauses,
            canonical,
            jobs=args.jobs,
        )
        console.print_warning("this may take some time.")
        deadline = SolverDeadline(args.timeout)
        try:
            solution = next_solution(view, deadline)
        except SolverTimeout:
            exit_solver_timeout(args.timeout_status_file)

        _, bn, configs = solution

        if normalized_to_original_gene_names:
            for old, new in normalized_to_original_gene_names.items():
                bn.rename(old, new)

        if "trapspace" in predicate_configs:
            for cfg_name in predicate_configs["trapspace"]:
                cfg_state = configs[cfg_name]
                trapspace = bn.principal_trapspace(cfg_state)
                configs[cfg_name] = {
                    key: value for key, value in trapspace.items() if value != "*"
                }

        for old, new in rename_cfgs.items():
            configs[new] = configs.pop(old)

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
            console.print_task(
                "enumerating Boolean network solutions "
                f"(kind=subset-minimal, limit={args.limit})"
            )
        else:
            console.print_task(
                "enumerating Boolean network solutions (kind=subset-minimal)"
            )

        print_node_reference(*get_node_sets(bo))
        console.print_warning("this may take some time.")

        view = bonesis.InfluenceGraphView(
            bo,
            solutions="subset-minimal",
            extra=("boolean-network", "configurations"),
            limit=args.limit if args.limit is not None else 0,
            progress=ptqdm,
            **get_subset_minimal_clingo_settings(args.jobs),
        )
        view.standalone(output_filename=args.asp)

        deadline = SolverDeadline(args.timeout)
        try:
            bns = run_bn_view(
                view=view,
                outdir=args.solution,
                config_formats=args.config_formats,
                graph_formats=args.graph_formats,
                normalized_to_original_gene_names=normalized_to_original_gene_names,
                trapspace_configurations=predicate_configs.get("trapspace", []),
                rename_cfgs=rename_cfgs,
                remove_isolated_nodes=args.remove_isolated_nodes,
                deadline=deadline,
            )
        except SolverTimeout:
            exit_solver_timeout(args.timeout_status_file)

    elif args.action == "diverse":
        if args.limit not in [None, 0]:
            console.print_task(
                "sampling Boolean network solutions " f"(kind=sparsest, limit={args.limit})"
            )
        else:
            console.print_task("sampling Boolean network solutions (kind=sparsest)")

        print_node_reference(*get_node_sets(bo))
        console.print_warning("this may take some time.")

        view = bonesis.DiverseBooleanNetworksView(
            bo,
            extra=("configurations",),
            limit=args.limit if args.limit is not None else 0,
            progress=ptqdm,
        )
        view.standalone(output_filename=args.asp)

        deadline = SolverDeadline(args.timeout)
        try:
            bns = run_bn_view(
                view=view,
                outdir=args.solution,
                config_formats=args.config_formats,
                graph_formats=args.graph_formats,
                normalized_to_original_gene_names=normalized_to_original_gene_names,
                trapspace_configurations=predicate_configs.get("trapspace", []),
                rename_cfgs=rename_cfgs,
                remove_isolated_nodes=args.remove_isolated_nodes,
                deadline=deadline,
            )
        except SolverTimeout:
            exit_solver_timeout(args.timeout_status_file)

    if args.action in ["submin", "diverse"]:
        write_ensemble_influence_graphs(
            bns=bns,
            components=bo.domain.nodes,
            outdir=Path(args.solution) / "influence_graph",
        )


if __name__ == "__main__":
    main()
