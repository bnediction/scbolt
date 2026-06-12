#!/usr/bin/env python

from typing import Any, Callable, Optional, Mapping, Iterable, Sequence
from collections import defaultdict

import sys
import os
import std
import argparse
import cli
import json
from pathlib import Path

from tqdm import tqdm

import pandas as pd

import bonesis
from bonesis.asp_encoding import clingo_encode
from mpbn import MPBooleanNetwork

import bonesistools as bt

from utils import get_cfg, load_bonesis_code, load_prior_network

bonesis.settings["quiet"] = True

DISABLE_TQDM = os.getenv("TQDM_DISABLE", "0") == "1"
TQDM_TO_TTY = os.getenv("TQDM_TO_TTY", "0") == "1"
script_name = Path(__file__).name


class ptqdm(tqdm):
    score_formatter: Callable[[Sequence[int]], Mapping[str, str]] | None = None
    initial_postfix: Mapping[str, str] | None = None

    def __init__(self, *args, **kwargs):

        kwargs.setdefault("leave", True)

        self._tqdm_file = None
        if TQDM_TO_TTY:
            try:
                self._tqdm_file = open("/dev/tty", "w")
                kwargs.setdefault("file", self._tqdm_file)
            except OSError:
                pass
        else:
            kwargs.setdefault("file", sys.stdout)

        if type(self).initial_postfix is not None:
            kwargs.setdefault("postfix", type(self).initial_postfix)
        kwargs.setdefault("disable", DISABLE_TQDM)
        super().__init__(*args, **kwargs)

    def close(self):
        super().close()
        if self._tqdm_file is not None:
            self._tqdm_file.close()
            self._tqdm_file = None

    def set_postfix(self, ordered_dict=None, refresh=True, **kwargs):
        score_formatter = type(self).score_formatter
        if (
            score_formatter is not None
            and ordered_dict is not None
            and "score" in ordered_dict
        ):
            ordered_dict = score_formatter(ordered_dict["score"])
        return super().set_postfix(
            ordered_dict=ordered_dict,
            refresh=refresh,
            **kwargs,
        )


def read_gene_list(infile: str | Path | None) -> list[str]:
    if infile is None:
        return []
    with open(infile) as file:
        return [line.rstrip() for line in file if line.rstrip()]


def make_filter_nodes_score_formatter(
    important_total: int,
    node_total: int,
) -> Callable[[Sequence[int]], Mapping[str, str]]:
    def format_score(score: Sequence[int]) -> Mapping[str, str]:
        values = [abs(int(value)) for value in score]
        fields = {}

        if important_total and len(values) >= 2:
            fields["important"] = f"{values[0]}/{important_total}"
            fields["total"] = f"{values[1]}/{node_total}"
        elif values:
            fields["total"] = f"{values[-1]}/{node_total}"

        return fields or {"score": str(list(score))}

    return format_score


def make_filter_consts_score_formatter(
    node_total: int,
    important_total: int = 0,
) -> Callable[[Sequence[int]], Mapping[str, str]]:
    def format_score(score: Sequence[int]) -> Mapping[str, str]:
        values = [abs(int(value)) for value in score]
        if not values:
            return {"score": str(list(score))}

        removed_nodes = values[-2] if important_total and len(values) >= 2 else values[-1]
        kept_nodes = max(node_total - removed_nodes, 0)
        fields = {"total": f"{kept_nodes}/{node_total}"}
        if important_total and len(values) >= 2:
            fields = {
                "important": f"{values[-1]}/{important_total}",
                **fields,
            }
        return fields

    return format_score


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


def get_node_sets(bo) -> tuple[set, set, int]:
    nodes_in_data = set()
    for bin_nodes in bo.data.values():
        nodes_in_data.update(bin_nodes.keys())
    return nodes_in_data, set(bo.domain.nodes), bo.domain.number_of_edges()


def print_node_reference(nodes_in_data, nodes_in_domain, domain_edges, **kwargs):
    std.print_info(
        f"input graph: data nodes={len(nodes_in_data)}, "
        f"domain nodes={len(nodes_in_domain)}, domain edges={domain_edges}",
        **kwargs,
    )


def print_clingo_optimization(
    mode, strategy, max_clause, canonic, configuration=None, jobs=None, **kwargs
):
    options = []
    strategy = "unused" if mode == "ignore" or mode.startswith("enum,") else strategy
    if configuration is not None:
        options.append(f"clingo config={configuration}")
    options.extend(
        [
            f"clingo mode={mode}",
            f"clingo strategy={strategy}",
        ]
    )
    if jobs is not None:
        options.append(f"clingo jobs={jobs}")
    options.extend(
        [
            f"max clauses={max_clause}",
            f"canonic={canonic}",
        ]
    )
    std.print_info(f"optimization options: {', '.join(options)}", **kwargs)


def get_clingo_options(configuration=None, *extra_options):
    options = []
    if configuration:
        options.append(f"--configuration={configuration}")
    options.extend(option for option in extra_options if option)
    return options


def get_clingo_parallel_mode(value):
    if "," in value:
        return None, f"--parallel-mode={value}"
    return int(value), None


def get_filter_clingo_options(mode, strategy, configuration=None, *extra_options):
    options = get_clingo_options(configuration)
    if mode == "opt":
        options.extend(["--opt-mode=opt", f"--opt-strategy={strategy}"])
    elif mode.startswith("enum,"):
        options.append(f"--opt-mode={mode}")
    elif mode == "ignore":
        options.append("--opt-mode=ignore")
    options.extend(option for option in extra_options if option)
    return options


def get_filter_clingo_settings(mode, strategy, configuration=None, *extra_options):
    options = get_filter_clingo_options(mode, strategy, configuration, *extra_options)
    return {"clingo_options": options} if options else {}


def get_clingo_settings(*extra_options):
    options = get_clingo_options(None, *extra_options)
    return {"clingo_options": options} if options else {}


def get_subset_minimal_clingo_settings(jobs):
    parallel_jobs, parallel_option = get_clingo_parallel_mode(jobs)

    if parallel_option:
        return {"parallel": None, "clingo_options": [parallel_option]}
    if parallel_jobs <= 1:
        return {}

    return {
        "parallel": None,
        "clingo_options": [f"--parallel-mode={min(parallel_jobs, 14)}"],
    }


def format_node_coverage(name, kept, total):
    removed = total - kept
    pct = 0 if total == 0 else 100 * kept / total
    return f"{name}: kept={kept}/{total} ({pct:.1f}%), removed={removed}"


def print_node_solution(solution, nodes_in_data, nodes_in_domain, **kwargs):
    solution = set(solution)
    std.print_result(f"solution: nodes={len(solution)}", **kwargs)
    std.print_result(
        format_node_coverage("data", len(nodes_in_data & solution), len(nodes_in_data)),
        **kwargs,
    )
    std.print_result(
        format_node_coverage(
            "domain", len(nodes_in_domain & solution), len(nodes_in_domain)
        ),
        **kwargs,
    )


def write_node_solution(
    nodes: Iterable[str],
    outfile: Path,
    status_file: Path | None = None,
):
    n_nodes = 0
    with open(outfile, "w") as file:
        for node in nodes:
            file.write(f"{node}\n")
            n_nodes += 1

    if n_nodes > 0 and status_file is not None:
        with open(status_file, "w") as file:
            file.write("_PARTIAL_SOLUTIONS\n")


def close_progress(view, leave=None):
    progressbar = getattr(view, "_progressbar", None)
    if progressbar is not None:
        if leave is not None:
            progressbar.leave = leave
        progressbar.close()


def next_solution(view):
    try:
        solution = next(iter(view))
    except (KeyboardInterrupt, RuntimeError):
        close_progress(view)
        raise
    close_progress(view)
    return solution


def write_noi(bn: MPBooleanNetwork, outfile):
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


def to_bonesistools_boolean_network(bn: MPBooleanNetwork) -> bt.bpy.bn.BooleanNetwork:
    """Adapt MPBN only for bonesistools graph export APIs."""
    return bt.bpy.bn.BooleanNetwork(bn.copy())


def write_influence_graph(
    bn: MPBooleanNetwork,
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

    graph_bn = to_bonesistools_boolean_network(bn)

    if remove_isolated_nodes:
        for node in list(graph_bn):
            if graph_bn[node] in [graph_bn.ba.FALSE, graph_bn.ba.TRUE]:
                del graph_bn[node]

    graph = graph_bn.to_pydot()

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
    bn: MPBooleanNetwork,
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


def write_ensemble_influence_graph(
    bns: Sequence[MPBooleanNetwork],
    components: Iterable[str],
    outfile: str | Path,
) -> None:
    std.print_task(f"saving ensemble influence graph (file={outfile})")

    ensemble = bt.bpy.bn.BooleanNetworkEnsemble(components=components)
    for bn in bns:
        ensemble.append(to_bonesistools_boolean_network(bn))

    dot = ensemble.to_pydot(
        remove_isolated_nodes=True,
        show_edge_labels=False,
        node_style="stability",
    )

    dot.write(
        str(outfile),
        prog="dot",
        format="pdf",
    )

    return None


def run_bn_view(
    view: Any,
    outdir: str | Path,
    config_formats: Sequence[str],
    graph_formats: Sequence[str],
    normalized_to_original_gene_names: Optional[Mapping[str, str]] = None,
    trapspace_configurations: Optional[Sequence[Any]] = None,
    rename_cfgs: Optional[Mapping[Any, Any]] = None,
    remove_isolated_nodes: bool = False,
) -> list[MPBooleanNetwork]:
    """
    Enumerate, post-process and export Boolean network solutions produced by a
    BoNesis view.

    The function supports BoNesis views returning either Boolean networks
    directly or influence graphs with associated Boolean networks. For each
    solution, it restores original gene names when needed, appends the Boolean
    network to the returned list, converts trapspace-associated configurations
    into principal trap spaces, simplifies tuple-based configuration names, and
    writes the solution to a numbered output directory.

    Parameters
    ----------
    view:
        BoNesis view enumerating Boolean network solutions.
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
    list[MPBooleanNetwork]
        Exported Boolean network solutions.

    Raises
    ------
    TypeError
        If the view type is not supported.
    """

    outdir = Path(outdir)
    normalized_to_original_gene_names = normalized_to_original_gene_names or {}
    trapspace_configurations = trapspace_configurations or []
    rename_cfgs = rename_cfgs or {}

    bns = []

    try:
        for i, solution in enumerate(view):

            if isinstance(view, bonesis.DiverseBooleanNetworksView):
                bn, configs = solution

            elif isinstance(view, bonesis.InfluenceGraphView):
                _, bn, configs = solution

            else:
                raise TypeError(f"unsupported BoNesis view type: {type(view).__name__}")

            for old, new in normalized_to_original_gene_names.items():
                bn.rename(old, new)

            bns.append(bn)

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
    except KeyboardInterrupt:
        close_progress(view)
        raise
    else:
        close_progress(view)

    return bns


parser_description = """Infer Most Permissive Boolean Networks (MPBNs) using the BoNesis paradigm.

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
    prog="infer",
    description=parser_description,
    usage=(
        f"python {script_name} [filter-nodes | filter-consts | min | submin | diverse] "
        "<FILE> <FILE> [<args>]"
    ),
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "action",
    choices=["filter-nodes", "filter-consts", "min", "submin", "diverse"],
    metavar="[filter-nodes | filter-consts | min | submin | diverse]",
    help="BoNesis inference action to run",
)

parser.add_argument(
    "spec",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file containing model specifications in BoNesis language (format: txt)",
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
    help="input file storing important genes prioritized to appear (format: json or txt)",
)

parser.add_argument(
    "--mandatory-genes",
    dest="mandatory_genes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="input file storing mandatory genes forced to appear (format: json or txt)",
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
    help="output file storing ASP program/command (format: sh)",
)

parser.add_argument(
    "--solution",
    dest="solution",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE | PATH",
    help="output storing BoNesis solution (txt for filter-nodes/filter-consts, directory for min/submin/diverse)",
)

parser.add_argument(
    "--status",
    dest="status",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="optional output file storing the current inference status",
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

parser.add_argument(
    "--dorothea-levels",
    dest="dorothea_levels",
    nargs="+",
    choices=["A", "B", "C", "D"],
    default=None,
    metavar="[A | B | C | D]",
    help=(
        "DoRothEA confidence levels used when --domain dorothea "
        "(default: A B C for current API; A B C D for legacy API)"
    ),
)

parser.add_argument(
    "--geneinfo-version",
    dest="geneinfo_version",
    action=cli.Store_version,
    allow_current=False,
    allow_bundled=True,
    allow_date=False,
    allow_path=True,
    required=False,
    default="latest",
    help="NCBI gene_info source used for gene name standardization (default: latest)",
)

parser.add_argument(
    "--omnipath-version",
    dest="omnipath_version",
    action=cli.Store_version,
    allow_current=False,
    required=False,
    default="latest",
    help="OmniPath resource version used when --domain is collectri or dorothea (default: latest)",
)

parser.add_argument(
    "--hcop-version",
    dest="hcop_version",
    type=str,
    required=False,
    default="bundled",
    help="HCOP orthology version used when --domain is collectri or dorothea (default: bundled)",
)

parser.add_argument(
    "--dorothea-api",
    dest="dorothea_api",
    choices=["current", "legacy"],
    required=False,
    default="current",
    help="DoRothEA API flavor used when --domain dorothea (default: current)",
)

parser.add_argument(
    "--dorothea-compatibility",
    dest="dorothea_compatibility",
    action=cli.Store_boolean,
    required=False,
    default=True,
    help="reproduce decoupler DoRothEA duplicated-pair handling (default: true)",
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
    "--canonic",
    dest="canonic",
    action=cli.Store_boolean,
    required=False,
    default=None,
    help="use canonical logical function representation (default: false for filter-nodes/filter-consts; true for min/submin/diverse)",
)

parser.add_argument(
    "--minimize-self-loops",
    dest="minimize_self_loops",
    required=False,
    action="store_true",
    help="minimize the number of self loops",
)

parser.add_argument(
    "--clingo-configuration",
    dest="clingo_configuration",
    type=str,
    required=False,
    default=None,
    metavar="[auto | frumpy | jumpy | tweety | handy | crafty | trendy | many | FILE]",
    help="clingo default configuration passed as --configuration for filter-nodes/filter-consts; if not specified, BoNesis/Clingo defaults are used",
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
        "Graphviz layout programs used for exporting Boolean network "
        "associated influence graphs (default: none)"
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
    action=cli.Clingo_parallel_mode,
    required=False,
    default="1",
    metavar="INT",
    help="number of Clingo jobs (default: 1)",
)

args = parser.parse_args()

if args.bonesis_mode != "hard":
    std.print_warning(
        f"some constraints are removed (bonesis mode: {args.bonesis_mode})"
    )

clingo_parallel_jobs, clingo_parallel_option = get_clingo_parallel_mode(args.jobs)
bonesis.settings["parallel"] = clingo_parallel_jobs

genesyn = bt.dbs.ncbi.genesyn(
    organism=args.organism,
    version=args.geneinfo_version,
)

std.print_task(
    f"loading partially binarized metastates (file={std.format_path(args.mstates)})"
)

mstates_df = pd.read_csv(args.mstates, index_col=0, sep=args.sep).fillna(float("nan"))

mstates_cfg = get_cfg(mstates_df, axis="index")

std.print_task("initializing inference settings (engine=BoNesis)")

canonic = args.canonic
if canonic is None:
    canonic = False if args.action.startswith("filter") else True

pkn_options = {
    "canonic": canonic,
    "maxclause": args.max_clause,
}
if args.action == "filter-nodes":
    pkn_options["allow_skipping_nodes"] = True

grn = load_prior_network(
    args.domain,
    args.organism,
    genesyn,
    args.dorothea_levels,
    args.omnipath_version,
    args.hcop_version,
    args.dorothea_api,
    args.dorothea_compatibility,
)

if args.filter_grn:
    std.print_info(f"filtering prior network (genes={args.filter_grn})")
    with open(args.filter_grn) as fp:
        nodes = [line.strip() for line in fp.readlines()]
    grn = grn.subgraph(nodes)
    del nodes

pkn = bonesis.domains.InfluenceGraph(grn, **pkn_options)

bo = bonesis.BoNesis(pkn, mstates_cfg)

with open(args.spec, "r") as file:
    load_bonesis_code(
        bo,
        file.read(),
        filename=str(args.spec),
    )

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

    std.print_task("maximizing satisfiable nodes")

    bo.maximize_nodes()

    mandatory_genes = read_gene_list(args.mandatory_genes)
    for gene in mandatory_genes:
        bo.custom(f"node({clingo_encode(gene)}).")

    important_genes = set(read_gene_list(args.important_genes))
    important_genes_in_domain = important_genes & set(bo.domain.nodes)
    for gene in important_genes_in_domain:
        bo.custom(f"important_node({clingo_encode(gene)}).")

    bo.custom("#maximize { 1@100,N: important_node(N),node(N) }.")
    filter_nodes_score_formatter = make_filter_nodes_score_formatter(
        important_total=len(important_genes_in_domain),
        node_total=len(bo.domain.nodes),
    )
    ptqdm.score_formatter = filter_nodes_score_formatter
    ptqdm.initial_postfix = filter_nodes_score_formatter(
        [0, 0] if important_genes_in_domain else [0]
    )

    def intermediate_solution(nodes):
        write_node_solution(nodes, args.solution, args.status)

    clingo_opt_strategy = args.clingo_opt_strategy or "bb,dec"
    view = bonesis.NodesView(
        bo,
        mode=args.clingo_opt_mode,
        intermediate_model_cb=intermediate_solution,
        clingo_opt_strategy=clingo_opt_strategy,
        progress=ptqdm,
        **get_filter_clingo_settings(
            args.clingo_opt_mode,
            clingo_opt_strategy,
            args.clingo_configuration,
            clingo_parallel_option,
        ),
    )
    view.standalone(output_filename=args.asp)
    nodes_in_data, nodes_in_domain, domain_edges = get_node_sets(bo)

    if not new_constraints:
        std.print_info("no new constraints added; stopping", flush=True)
        write_node_solution(bo.domain.nodes, args.solution, args.status)
        sys.exit(0)

    print_node_reference(nodes_in_data, nodes_in_domain, domain_edges, flush=True)
    print_clingo_optimization(
        args.clingo_opt_mode,
        clingo_opt_strategy,
        args.max_clause,
        canonic,
        configuration=args.clingo_configuration or "auto",
        jobs=args.jobs,
        flush=True,
    )
    std.print_warning("this may take some time.", flush=True)
    try:
        solution = next_solution(view)
    except RuntimeError:
        if not args.solution.exists() or args.solution.stat().st_size == 0:
            raise
        with open(args.solution) as file:
            solution = [line.rstrip() for line in file if line.rstrip()]
        if not solution:
            raise
        std.print_debug(
            "selecting intermediate solution (reason=final model parsing failed, certification=partial/non-certified)",
            flush=True,
        )

    write_node_solution(solution, args.solution, args.status)

    print_node_solution(solution, nodes_in_data, nodes_in_domain, flush=True)

elif args.action == "filter-consts":

    std.print_task("maximizing strong constants")

    bo.maximize_strong_constants()
    if args.minimize_self_loops:
        bo.custom("edge(A,A) :- clause(A,_,A,_). #minimize { 1@10000,A: edge(A,A) }.")

    important_genes = set(read_gene_list(args.important_genes))
    important_genes_in_domain = important_genes & set(bo.domain.nodes)
    for gene in important_genes_in_domain:
        bo.custom(f"important_node({clingo_encode(gene)}).")

    if important_genes_in_domain:
        bo.custom(
            "#maximize { 1@1,N: important_node(N), node(N), "
            "not strong_constant(N) }."
        )

    clingo_opt_strategy = "usc"
    ptqdm.score_formatter = make_filter_consts_score_formatter(
        node_total=len(bo.domain.nodes),
        important_total=len(important_genes_in_domain),
    )
    ptqdm.initial_postfix = {"total": f"0/{len(bo.domain.nodes)}"}
    if important_genes_in_domain:
        ptqdm.initial_postfix = {
            "important": f"0/{len(important_genes_in_domain)}",
            **ptqdm.initial_postfix,
        }
    view = bonesis.NonStrongConstantNodesView(
        bo,
        mode=args.clingo_opt_mode,
        clingo_opt_strategy=clingo_opt_strategy,
        progress=ptqdm,
        **get_filter_clingo_settings(
            args.clingo_opt_mode,
            clingo_opt_strategy,
            args.clingo_configuration,
            "--opt-usc-shrink=inv",
            clingo_parallel_option,
        ),
    )
    view.standalone(output_filename=args.asp)

    nodes_in_data, nodes_in_domain, domain_edges = get_node_sets(bo)
    print_node_reference(nodes_in_data, nodes_in_domain, domain_edges)
    print_clingo_optimization(
        args.clingo_opt_mode,
        clingo_opt_strategy,
        args.max_clause,
        canonic,
        configuration=args.clingo_configuration or "auto",
        jobs=args.jobs,
    )
    std.print_warning("this may take some time.")
    solution = next_solution(view)

    write_node_solution(solution, args.solution, args.status)

    if important_genes_in_domain:
        std.print_result(
            f"important nodes: kept={len(set(solution) & important_genes_in_domain)}/"
            f"{len(important_genes_in_domain)}"
        )
    print_node_solution(solution, nodes_in_data, nodes_in_domain)

else:

    normalized_to_original_gene_names = {
        gene.replace("-", "_"): gene for gene in bo.domain.nodes if "-" in gene
    }
    if normalized_to_original_gene_names:
        std.print_debug(
            "restoring gene names "
            f"(phase=post-inference, reason=unsupported '-' characters, genes={'+'.join(f'{k}->{v}' for k, v in normalized_to_original_gene_names.items())})"
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
        renamed_configs = ", ".join(map(str, rename_cfgs))
        std.print_debug(
            "simplifying configuration names "
            f"(reason=tuple-based names, configurations={renamed_configs})"
        )

    if args.action == "min":

        std.print_task("computing Boolean network solution (objective=minimize edges)")

        bo.custom("edge(A,B) :- clause(B,_,A,_). #minimize { 1@1,A,B: edge(A,B) }.")
        bo.custom("#maximize { 1@10,N: constant(N) }.")

        if args.minimize_self_loops:
            bo.custom("#minimize { 1@100,A: edge(A,A) }.")

        clingo_opt_strategy = "usc"
        view = bonesis.InfluenceGraphView(
            bo,
            mode=args.clingo_opt_mode,
            clingo_opt_strategy=clingo_opt_strategy,
            extra=("boolean-network", "configurations"),
            progress=ptqdm,
        )
        view.standalone(output_filename=args.asp)

        print_node_reference(*get_node_sets(bo))
        print_clingo_optimization(
            args.clingo_opt_mode,
            clingo_opt_strategy,
            args.max_clause,
            canonic,
            jobs=args.jobs,
        )
        std.print_warning("this may take some time.")
        solution = next_solution(view)

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
                f"enumerating Boolean network solutions (kind=subset-minimal, limit={args.limit})"
            )
        else:
            std.print_task(
                "enumerating Boolean network solutions (kind=subset-minimal)"
            )

        print_node_reference(*get_node_sets(bo))
        std.print_warning("this may take some time.")

        view = bonesis.InfluenceGraphView(
            bo,
            solutions="subset-minimal",
            extra=("boolean-network", "configurations"),
            limit=args.limit if args.limit is not None else 0,
            progress=ptqdm,
            **get_subset_minimal_clingo_settings(args.jobs),
        )
        view.standalone(output_filename=args.asp)

        bns = run_bn_view(
            view=view,
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
            std.print_task(
                f"sampling Boolean network solutions (kind=sparsest, limit={args.limit})"
            )
        else:
            std.print_task("sampling Boolean network solutions (kind=sparsest)")

        print_node_reference(*get_node_sets(bo))
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
            outdir=args.solution,
            config_formats=args.config_formats,
            graph_formats=args.graph_formats,
            normalized_to_original_gene_names=normalized_to_original_gene_names,
            trapspace_configurations=predicate_configs.get("trapspace", []),
            rename_cfgs=rename_cfgs,
            remove_isolated_nodes=args.remove_isolated_nodes,
        )

    if args.action in ["submin", "diverse"]:
        write_ensemble_influence_graph(
            bns=bns,
            components=bo.domain.nodes,
            outfile=Path(args.solution) / "ensemble.pdf",
        )
