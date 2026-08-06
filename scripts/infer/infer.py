import argparse
import json
import shutil
import time
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from functools import partial
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import bonesis
import bonesistools as bt
import pandas as pd
from mpbn import MPBooleanNetwork
from scbolt import cli, console
from scbolt.inference import write_influence_graph
from scbolt.inference._enumeration import (
    BooleanNetworkEnumerationCheckpoint,
    SignedEdge,
    build_subset_minimal_blockers,
    elapsed_since,
    enumeration_fingerprint,
)
from scbolt.inference._selection import (
    BooleanNetworkProgress,
    fork_bonesis,
    ptqdm,
)
from scbolt.inference._witness import (
    apply_structural_witness_heuristics,
    canonicalize_structural_witness,
    read_structural_witness,
)
from scbolt.runtime import (
    SolverDeadline,
    SolverMemorySupervisor,
    SolverTimeout,
    close_solver_progress,
    current_rss_bytes,
    exit_solver_timeout,
    format_memory_size,
    get_clingo_parallel_mode,
    get_subset_minimal_clingo_settings,
    iter_solutions,
    next_solution,
    parse_memory_limit,
    release_unused_memory,
    reset_solver_timeout_status,
)
from utils import (
    add_bonesis_arguments,
    apply_bonesis_mode,
    get_node_sets,
    initialize_bonesis,
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


def signed_influence_edges(
    graph: Any,
    rename_nodes: Mapping[str, str] | None = None,
) -> frozenset[SignedEdge]:
    """Return signed influence edges with optional node-name restoration."""

    rename_nodes = rename_nodes or {}
    return frozenset(
        (
            rename_nodes.get(str(source), str(source)),
            rename_nodes.get(str(target), str(target)),
            int(data["sign"]),
        )
        for source, target, data in graph.edges(data=True)
    )


def package_version(name: str) -> str:
    """Return an installed package version for checkpoint compatibility."""

    try:
        return version(name)
    except PackageNotFoundError:
        return "missing"


def subset_minimal_fingerprint(
    args: argparse.Namespace,
    *,
    canonical: bool,
) -> str:
    """Fingerprint inputs defining subset-minimal solutions and their exports."""

    files = [args.spec, args.mstates]
    for path in (args.filter_grn, args.initial_witness):
        if path is not None and path.is_file():
            files.append(path)

    domain = args.domain
    if isinstance(domain, Path):
        files.append(domain)
        domain = "custom"

    settings = {
        "action": "submin",
        "bonesis": package_version("bonesis"),
        "bonesistools": package_version("bonesistools"),
        "bounded_nonreach": args.bounded_nonreach,
        "canonical": canonical,
        "config_formats": args.config_formats,
        "domain": domain,
        "dorothea_api": args.dorothea_api,
        "dorothea_compatibility": args.dorothea_compatibility,
        "dorothea_levels": args.dorothea_levels,
        "geneinfo_version": str(args.geneinfo_version),
        "graph_formats": args.graph_formats,
        "hcop_version": str(args.hcop_version),
        "limit": args.limit,
        "max_clauses": args.max_clauses,
        "mpbn": package_version("mpbn"),
        "omnipath_version": str(args.omnipath_version),
        "organism": args.organism,
        "remove_isolated_nodes": args.remove_isolated_nodes,
        "separator": args.sep,
    }
    return enumeration_fingerprint(files, settings)


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
            to_bonesistools_boolean_network(bn),
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
    normalized_to_original_gene_names: Mapping[str, str] | None = None,
    trapspace_configurations: Sequence[Any] | None = None,
    rename_cfgs: Mapping[Any, Any] | None = None,
    remove_isolated_nodes: bool = False,
    deadline: SolverDeadline | None = None,
    checkpoint: BooleanNetworkEnumerationCheckpoint | None = None,
    start_index: int = 0,
    on_solution_written: Callable[
        [int, MPBooleanNetwork, Collection[SignedEdge]], None
    ]
    | None = None,
) -> list[MPBooleanNetwork]:
    """Enumerate, post-process and export Boolean network view solutions."""

    outdir = Path(outdir)
    normalized_to_original_gene_names = normalized_to_original_gene_names or {}
    trapspace_configurations = trapspace_configurations or []
    rename_cfgs = rename_cfgs or {}

    bns = []

    solutions = iter_solutions(view, deadline)
    try:
        for offset, solution in enumerate(solutions, start=1):
            i = start_index + offset
            if isinstance(view, bonesis.DiverseBooleanNetworksView):
                bn, configs = solution
                influence_edges = frozenset()
            elif isinstance(view, bonesis.InfluenceGraphView):
                influence_graph, bn, configs = solution
                influence_edges = signed_influence_edges(influence_graph)
            else:
                raise TypeError(f"unsupported BoNesis view type: {type(view).__name__}")

            for old, new in normalized_to_original_gene_names.items():
                bn.rename(old, new)

            # Keep bn-submin/bn-diverse configurations as returned by BoNesis.
            # for cfg_name in trapspace_configurations:
            #     cfg_state = configs[cfg_name]
            #     ts = bn.principal_trapspace(cfg_state)
            #     configs[cfg_name] = {k: v for k, v in ts.items() if v != "*"}

            for old, new in rename_cfgs.items():
                configs[new] = configs.pop(old)

            if checkpoint is None:
                write_solution(
                    bn=bn,
                    configurations=configs,
                    outdir=outdir / str(i),
                    config_formats=config_formats,
                    graph_formats=graph_formats,
                    remove_isolated_nodes=remove_isolated_nodes,
                )
            else:
                with checkpoint.atomic_solution_directory(i) as solution_dir:
                    write_solution(
                        bn=bn,
                        configurations=configs,
                        outdir=solution_dir,
                        config_formats=config_formats,
                        graph_formats=graph_formats,
                        remove_isolated_nodes=remove_isolated_nodes,
                    )

            bns.append(bn)
            if on_solution_written is not None:
                on_solution_written(i, bn, influence_edges)
    finally:
        solutions.close()
        close_solver_progress(view)

    return bns


def recover_subset_minimal_networks(
    solution_directories: Sequence[Path],
    *,
    original_to_normalized_gene_names: Mapping[str, str],
) -> tuple[list[MPBooleanNetwork], list[frozenset[SignedEdge]]]:
    """Load complete networks and their internal signed influence graphs."""

    networks = []
    influence_graphs = []
    for directory in solution_directories:
        network = MPBooleanNetwork(str(directory / "model.bnet"))
        networks.append(network)
        influence_graphs.append(
            signed_influence_edges(
                network.influence_graph(),
                rename_nodes=original_to_normalized_gene_names,
            )
        )
    return networks, influence_graphs


def enumerate_subset_minimal_networks(
    bo: bonesis.BoNesis,
    args: argparse.Namespace,
    *,
    canonical: bool,
    normalized_to_original_gene_names: Mapping[str, str],
    trapspace_configurations: Sequence[Any],
    rename_cfgs: Mapping[Any, Any],
) -> list[MPBooleanNetwork]:
    """Enumerate subset-minimal networks with memory-aware checkpointing."""

    outdir = Path(args.solution)
    checkpoint = BooleanNetworkEnumerationCheckpoint(
        outdir,
        config_formats=args.config_formats,
        graph_formats=args.graph_formats,
        fingerprint=subset_minimal_fingerprint(args, canonical=canonical),
    )
    recovery = checkpoint.prepare(
        force_restart=(outdir / ".scbolt.json").is_file(),
    )
    if recovery.reset_reason is not None:
        message = (
            "restarting Boolean network enumeration "
            f"(reason={recovery.reset_reason})"
        )
        if recovery.reset_reason == "requested rebuild":
            console.print_debug(message)
        else:
            console.print_warning(message)
    if recovery.discarded_directories:
        discarded = ",".join(path.name for path in recovery.discarded_directories)
        console.print_warning(
            "discarding incomplete Boolean network outputs "
            f"(solutions={discarded})"
        )

    shutil.rmtree(outdir / "influence_graph", ignore_errors=True)
    original_to_normalized_gene_names = {
        original: normalized
        for normalized, original in normalized_to_original_gene_names.items()
    }
    networks, influence_graphs = recover_subset_minimal_networks(
        recovery.solution_directories,
        original_to_normalized_gene_names=original_to_normalized_gene_names,
    )
    if networks:
        console.print_info(
            "resuming subset-minimal enumeration "
            f"(generated={len(networks)})"
        )

    previous_elapsed = recovery.elapsed_seconds
    active_started_at = time.monotonic()
    deadline = SolverDeadline(args.timeout)
    parallel_jobs, _ = get_clingo_parallel_mode(args.jobs)
    if parallel_jobs is None:
        jobs_value, parallel_mode = args.jobs.split(",", maxsplit=1)
        current_jobs = int(jobs_value)
    else:
        current_jobs = min(parallel_jobs, 14)
        parallel_mode = None
    stalled_restarts = 0

    def cumulative_elapsed() -> float:
        return elapsed_since(active_started_at, previous_elapsed)

    def solution_written(
        index: int,
        network: MPBooleanNetwork,
        influence_edges: Collection[SignedEdge],
    ) -> None:
        networks.append(network)
        influence_graphs.append(frozenset(influence_edges))
        checkpoint.write_state(
            solution_count=index,
            elapsed_seconds=cumulative_elapsed(),
        )

    while args.limit in {None, 0} or len(networks) < args.limit:
        working_bo = fork_bonesis(
            bo,
            max_clause=args.max_clauses,
        )
        blocker_program = build_subset_minimal_blockers(influence_graphs)
        if blocker_program:
            working_bo.custom(blocker_program)

        if parallel_mode is None:
            parallel_value = str(current_jobs)
            working_bo.settings["parallel"] = current_jobs
        else:
            parallel_value = f"{current_jobs},{parallel_mode}"
        clingo_settings = get_subset_minimal_clingo_settings(parallel_value)
        remaining_limit = (
            args.limit - len(networks)
            if args.limit not in {None, 0}
            else 0
        )
        supervisor = (
            SolverMemorySupervisor(args.memory_limit)
            if args.memory_limit is not None
            else None
        )
        progress_started_at = time.time() - cumulative_elapsed()
        view = bonesis.InfluenceGraphView(
            working_bo,
            solutions="subset-minimal",
            extra=("boolean-network", "configurations"),
            limit=remaining_limit,
            progress=partial(
                BooleanNetworkProgress,
                label="Boolean network enumeration",
                limit=args.limit,
                initial=len(networks),
                started_at=progress_started_at,
                supervisor=supervisor,
            ),
            **clingo_settings,
        )
        view.standalone(output_filename=args.asp)

        generated_before = len(networks)
        runtime_error = None
        if supervisor is not None:
            supervisor.start(view)
        try:
            run_bn_view(
                view=view,
                outdir=outdir,
                config_formats=args.config_formats,
                graph_formats=args.graph_formats,
                normalized_to_original_gene_names=(
                    normalized_to_original_gene_names
                ),
                trapspace_configurations=trapspace_configurations,
                rename_cfgs=rename_cfgs,
                remove_isolated_nodes=args.remove_isolated_nodes,
                deadline=deadline,
                checkpoint=checkpoint,
                start_index=generated_before,
                on_solution_written=solution_written,
            )
        except RuntimeError as error:
            runtime_error = error
        finally:
            if supervisor is not None:
                supervisor.stop()

        pressure = supervisor.memory_pressure() if supervisor is not None else None
        if runtime_error is not None:
            if pressure is None:
                raise runtime_error
            runtime_error.__traceback__ = None
            runtime_error = None

        memory_before_release = current_rss_bytes()
        del view
        del working_bo
        release_unused_memory()
        memory_after_release = current_rss_bytes()

        if pressure is None:
            break
        if args.limit not in {None, 0} and len(networks) >= args.limit:
            break

        console.print_warning(
            "enumeration memory pressure "
            f"(rss={format_memory_size(pressure.rss)}, "
            f"projected={format_memory_size(pressure.projected_rss)}, "
            f"limit={format_memory_size(pressure.limit)})"
        )
        console.print_debug(
            "checkpointed Boolean networks "
            f"(complete={len(networks)})"
        )
        if memory_before_release is not None and memory_after_release is not None:
            released = max(0, memory_before_release - memory_after_release)
            console.print_debug(
                "enumeration solver memory "
                f"(released={format_memory_size(released)}, "
                f"remaining={format_memory_size(memory_after_release)})"
            )

        generated_in_cycle = len(networks) - generated_before
        if generated_in_cycle == 0:
            stalled_restarts += 1
            if current_jobs > 1:
                current_jobs = max(1, current_jobs // 2)
            elif stalled_restarts > 1:
                raise RuntimeError(
                    "enumeration cannot make progress within the configured "
                    f"memory budget ({format_memory_size(args.memory_limit)})"
                )
        else:
            stalled_restarts = 0

        next_parallel_value = (
            str(current_jobs)
            if parallel_mode is None
            else f"{current_jobs},{parallel_mode}"
        )
        console.print_info(
            "restarting subset-minimal portfolio "
            f"(jobs={next_parallel_value}, generated={len(networks)})"
        )

    checkpoint.write_state(
        solution_count=len(networks),
        elapsed_seconds=cumulative_elapsed(),
    )
    return networks


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
        "--memory-limit",
        dest="memory_limit",
        type=parse_memory_limit,
        required=False,
        default=None,
        metavar="MEMORY",
        help=(
            "memory budget for resumable subset-minimal enumeration; "
            "integers are interpreted as GB"
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

        console.print_node_reference(*get_node_sets(bo))
        console.print_solver_options(
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

        console.print_node_reference(*get_node_sets(bo))
        console.print_warning("this may take some time.")

        try:
            bns = enumerate_subset_minimal_networks(
                bo,
                args,
                canonical=canonical,
                normalized_to_original_gene_names=(
                    normalized_to_original_gene_names
                ),
                trapspace_configurations=predicate_configs.get(
                    "trapspace", []
                ),
                rename_cfgs=rename_cfgs,
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

        console.print_node_reference(*get_node_sets(bo))
        console.print_warning("this may take some time.")

        view = bonesis.DiverseBooleanNetworksView(
            bo,
            extra=("configurations",),
            limit=args.limit if args.limit is not None else 0,
            progress=partial(
                BooleanNetworkProgress,
                label="Boolean network sampling",
                limit=args.limit,
            ),
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
        console.print_result(f"Boolean networks: generated={len(bns)}")
        write_ensemble_influence_graphs(
            bns=bns,
            components=bo.domain.nodes,
            outdir=Path(args.solution) / "influence_graph",
        )


if __name__ == "__main__":
    main()
