import argparse
import inspect
import os
import sys
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from numbers import Number
from pathlib import Path
from typing import Any

import bonesis
import bonesistools as bt
import pandas as pd
from pandas import DataFrame
from pandas._typing import Axis
from scbolt import cli, console
from scbolt.runtime import get_clingo_parallel_mode, parse_solver_timeout
from tqdm import tqdm

DISABLE_TQDM = os.getenv("TQDM_DISABLE", "0") == "1"
TQDM_TO_TTY = os.getenv("TQDM_TO_TTY", "0") == "1"


class ptqdm(tqdm):
    score_formatter: Callable[[Sequence[int]], Mapping[str, str]] | None = None
    initial_postfix: Mapping[str, str] | None = None

    def __init__(self, *args, **kwargs):
        kwargs["leave"] = False
        kwargs.setdefault("dynamic_ncols", True)

        self._tqdm_file_context = ExitStack()
        self._tqdm_file = None
        if TQDM_TO_TTY and "file" not in kwargs:
            try:
                self._tqdm_file = self._tqdm_file_context.enter_context(
                    console.open_terminal_stream()
                )
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
            self._tqdm_file_context.close()
            self._tqdm_file = None

    def set_postfix(self, ordered_dict=None, refresh=True, **kwargs):
        score_formatter = type(self).score_formatter
        if (
            score_formatter is not None
            and ordered_dict is not None
            and "score" in ordered_dict
        ):
            ordered_dict = score_formatter(ordered_dict["score"])

        postfix = OrderedDict([] if ordered_dict is None else ordered_dict)
        for key in sorted(kwargs):
            postfix[key] = kwargs[key]
        for key, value in postfix.items():
            if isinstance(value, Number):
                postfix[key] = self.format_num(value)
            elif not isinstance(value, str):
                postfix[key] = str(value)

        # tqdm strips string values, which removes deliberate numeric padding.
        self.postfix = ", ".join(
            f"{key}={value}" for key, value in postfix.items()
        )
        if refresh:
            self.refresh()


def add_bonesis_arguments(parser: argparse.ArgumentParser) -> None:
    """Add model, domain and solver arguments shared by selection and inference."""

    parser.add_argument(
        "spec",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help=(
            "input file containing model specifications in BoNesis language "
            "(format: txt)"
        ),
    )
    parser.add_argument(
        "mstates",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help=("input file storing partially binarized metastates " "(format: csv)"),
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
        help="output storing the BoNesis solution",
    )
    parser.add_argument(
        "--timeout",
        dest="timeout",
        type=parse_solver_timeout,
        required=False,
        default=0.0,
        metavar="DURATION",
        help=(
            "maximum total solver runtime; suffixes s, m, h and d are "
            "supported, and 0 disables the limit (default: 0)"
        ),
    )
    parser.add_argument(
        "--timeout-status-file",
        dest="timeout_status_file",
        type=lambda x: Path(x).resolve(),
        required=False,
        default=None,
        metavar="FILE",
        help=argparse.SUPPRESS,
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
            "(default: A B C for modern API; A B C D for legacy API)"
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
        default="bundled",
        help=(
            "NCBI gene_info source used for gene name standardization "
            "(default: bundled)"
        ),
    )
    parser.add_argument(
        "--omnipath-version",
        dest="omnipath_version",
        action=cli.Store_version,
        allow_current=False,
        required=False,
        default="latest",
        help=(
            "OmniPath resource version used when --domain is collectri or "
            "dorothea (default: latest)"
        ),
    )
    parser.add_argument(
        "--hcop-version",
        dest="hcop_version",
        type=str,
        required=False,
        default="bundled",
        help=(
            "HCOP orthology version used when --domain is collectri or "
            "dorothea (default: bundled)"
        ),
    )
    parser.add_argument(
        "--dorothea-api",
        dest="dorothea_api",
        choices=["modern", "legacy"],
        required=False,
        default="modern",
        help="DoRothEA API flavor used when --domain dorothea (default: modern)",
    )
    parser.add_argument(
        "--dorothea-compatibility",
        dest="dorothea_compatibility",
        action=cli.Store_boolean,
        required=False,
        default=True,
        help=(
            "reproduce decoupler DoRothEA duplicated-pair handling " "(default: true)"
        ),
    )
    parser.add_argument(
        "--bonesis-mode",
        dest="bonesis_mode",
        action=cli.Bonesis_mode,
    )
    parser.add_argument(
        "--max-clauses",
        dest="max_clauses",
        type=int,
        required=False,
        default=8,
        metavar="INT",
        help=(
            "maximum number of conjunctive terms joined by OR in each "
            "Boolean update function "
            "(default: 8)"
        ),
    )
    parser.add_argument(
        "--bounded-nonreach",
        dest="bounded_nonreach",
        action=cli.Range,
        type=int,
        min=1,
        required=False,
        default=None,
        help=(
            "number of certificate iterations used for non-reachability "
            "constraints; omission uses the regulatory-domain size"
        ),
    )
    parser.add_argument(
        "--canonical",
        dest="canonical",
        action=cli.Store_boolean,
        required=False,
        default=None,
        help=(
            "normalize DNF term ordering and reject directly subsumed terms"
        ),
    )
    parser.add_argument(
        "--minimize-self-loops",
        dest="minimize_self_loops",
        required=False,
        action="store_true",
        help="minimize the number of self loops",
    )
    parser.add_argument(
        "--clingo-mode",
        dest="clingo_mode",
        action=cli.Clingo_mode,
        required=False,
        default="optN",
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
        "--jobs",
        dest="jobs",
        action=cli.Clingo_parallel_mode,
        required=False,
        default="1",
        metavar="INT",
        help="number of Clingo jobs (default: 1)",
    )


def initialize_bonesis(
    args: argparse.Namespace,
    *,
    allow_skipping_nodes: bool,
    default_canonical: bool,
    forbidden_nodes_file: Path | None = None,
) -> tuple[bonesis.BoNesis, bool, str | None]:
    """Build the BoNesis problem shared by selection and inference commands."""

    if args.bonesis_mode != "hard":
        console.print_warning(
            f"some constraints are removed (bonesis mode: {args.bonesis_mode})"
        )

    clingo_parallel_jobs, clingo_parallel_option = get_clingo_parallel_mode(args.jobs)
    bonesis.settings["parallel"] = clingo_parallel_jobs

    identifiers = bt.resources.ncbi.identifiers(
        organism=args.organism,
        version=args.geneinfo_version,
    )
    console.print_task(
        "loading partially binarized metastates "
        f"(file={console.format_path(args.mstates)})"
    )
    mstates_df = pd.read_csv(args.mstates, index_col=0, sep=args.sep).fillna(
        float("nan")
    )
    mstates_cfg = get_cfg(mstates_df, axis="index")

    console.print_task("initializing BoNesis inference (engine=BoNesis)")

    canonical = args.canonical
    if canonical is None:
        canonical = default_canonical

    pkn_options = {
        "canonic": canonical,
        "maxclause": args.max_clauses,
    }
    if allow_skipping_nodes:
        pkn_options["allow_skipping_nodes"] = True

    grn = load_prior_network(
        args.domain,
        args.organism,
        identifiers,
        args.dorothea_levels,
        args.omnipath_version,
        args.hcop_version,
        args.dorothea_api,
        args.dorothea_compatibility,
    )
    if forbidden_nodes_file is not None:
        with open(forbidden_nodes_file) as file:
            forbidden_nodes = {
                line.rstrip() for line in file if line.rstrip()
            }
        forbidden_nodes = set(identifiers(forbidden_nodes))
        grn = remove_forbidden_nodes(grn, forbidden_nodes)
    if args.filter_grn:
        console.print_info(f"filtering prior network (genes={args.filter_grn})")
        with open(args.filter_grn) as file:
            nodes = [line.strip() for line in file]
        grn = grn.subgraph(nodes)

    pkn = bonesis.domains.InfluenceGraph(grn, **pkn_options)
    bo = bonesis.BoNesis(pkn, mstates_cfg)
    if args.bounded_nonreach is not None:
        bo.set_constant("bounded_nonreach", args.bounded_nonreach)
    with open(args.spec, "r") as file:
        load_bonesis_code(
            bo,
            file.read(),
            filename=str(args.spec),
        )

    return bo, canonical, clingo_parallel_option


def apply_bonesis_mode(bo: bonesis.BoNesis, mode: str) -> bool:
    """Remove constraints excluded by a soft or relaxed selection stage."""

    removed_predicates = set()
    if mode == "soft":
        new_constraints = True
        removed_predicates = {
            "final_nonreach",
            "nonreach",
            "all_fixpoints",
            "allreach",
        }
    elif mode == "relaxed":
        new_constraints = any(
            predicate in {"final_nonreach", "nonreach"}
            for predicate, _, _ in bo.manager.properties
        )
        removed_predicates = {"all_fixpoints", "allreach"}
    else:
        new_constraints = any(
            predicate in {"all_fixpoints", "allreach"}
            for predicate, _, _ in bo.manager.properties
        )

    if removed_predicates:
        bo.manager.properties = [
            prop
            for prop in bo.manager.properties.copy()
            if prop[0] not in removed_predicates
        ]

    return new_constraints


def get_node_sets(bo: bonesis.BoNesis) -> tuple[set, set, int]:
    """Return data nodes, domain nodes and the domain edge count."""

    nodes_in_data = set()
    for bin_nodes in bo.data.values():
        nodes_in_data.update(bin_nodes.keys())
    return nodes_in_data, set(bo.domain.nodes), bo.domain.number_of_edges()


def get_cfg(df: DataFrame, axis: Axis = 0, identifiers: Any | None = None) -> dict:
    """
    Convert configurations from dataframe format into dictionary format.

    Parameters
    ----------
    df: pd.DataFrame
        DataFrame object.
    axis: pd.Axis (default: 0)
        Whether configuration names are df.index (0 or 'index') or df.obs (1 or 'column').
    identifiers: callable (optional, default: None)
        Gene identifier converter used for standardizing gene names.

    Returns
    -------
    Return Dict object.
    """

    if axis in [0, "index"]:
        df = df.copy().T
    elif axis in [1, "column"]:
        pass
    else:
        raise ValueError(
            f"invalid value for 'axis' (got {axis}, expected 'index' or 'column')"
        )

    if identifiers is not None:
        identifiers(df, axis=0, copy=False)

    return {config: genes.to_dict() for config, genes in df.items()}


def load_bonesis_code(
    bo: bonesis.BoNesis,
    code: str,
    filename: str = "<bonesis>",
    namespace: dict | None = None,
) -> dict:
    """
    Load BoNesis DSL code through the safe AST validator.

    The `bo` symbol is kept in the namespace for compatibility with older
    scBOLT specifications using `bo.obs(...)`, while the BoNesis language
    symbols also allow direct DSL calls such as `obs(...)`.
    """

    if namespace is None:
        namespace = {}
    namespace.setdefault("bo", bo)

    try:
        return bo.load_code(
            code,
            defs=namespace,
            safe=True,
            filename=filename,
        )
    except TypeError as error:
        if "unexpected keyword argument" in str(error):
            raise RuntimeError(
                "safe BoNesis DSL loading requires BoNesis with "
                "`load_code(..., safe=True)` support"
            ) from error
        raise


def load_prior_network(
    domain: str,
    organism: str,
    identifiers: Any,
    dorothea_levels: Sequence[str] | None = None,
    omnipath_version: str = "latest",
    hcop_version: str = "bundled",
    dorothea_api: str = "modern",
    dorothea_compatibility: bool = True,
):
    if domain == "collectri":
        console.print_info(
            f"loading CollecTRI prior network "
            f"(organism={organism}, version={omnipath_version}, "
            f"hcop={hcop_version})"
        )
        kwargs = {
            "organism": organism,
            "version": omnipath_version,
            "identifiers": identifiers,
        }
        if (
            "hcop_version"
            in inspect.signature(bt.resources.omnipath.collectri).parameters
        ):
            kwargs["hcop_version"] = hcop_version
        return bt.resources.omnipath.collectri(**kwargs)

    if domain == "dorothea":
        flavor = {"modern": "modern", "legacy": "legacy"}[dorothea_api]
        if dorothea_levels is None:
            levels = ["A", "B", "C", "D"] if flavor == "legacy" else ["A", "B", "C"]
        else:
            levels = list(dorothea_levels)
        console.print_info(
            f"loading DoRothEA prior network "
            f"(organism={organism}, levels={','.join(levels)}, "
            f"version={omnipath_version}, hcop={hcop_version}, "
            f"flavor={flavor}, compatibility={str(dorothea_compatibility).lower()})"
        )
        return bt.resources.omnipath.dorothea(
            organism=organism,
            levels=levels,
            version=omnipath_version,
            hcop_version=hcop_version,
            flavor=flavor,
            compatibility=dorothea_compatibility,
            identifiers=identifiers,
        )

    console.print_task(f"loading custom prior network (file={console.format_path(domain)})")
    return bt.logic.io.read_influence_graph(
        file=domain,
        identifiers=identifiers,
    )


def remove_forbidden_nodes(grn: Any, forbidden_nodes: set[str]) -> Any:
    """Return the prior network induced by nodes that are not forbidden."""

    prior_nodes = set(grn.nodes)
    forbidden_in_domain = prior_nodes & forbidden_nodes
    if not forbidden_in_domain:
        return grn

    kept_nodes = len(prior_nodes) - len(forbidden_in_domain)
    console.print_info(
        "removing forbidden nodes from prior network "
        f"(kept={kept_nodes}/{len(prior_nodes)} "
        f"({100 * kept_nodes / len(prior_nodes):.1f}%), "
        f"removed={len(forbidden_in_domain)})"
    )
    return grn.subgraph(prior_nodes - forbidden_nodes)
