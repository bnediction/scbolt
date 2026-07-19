#!/usr/bin/env python

import argparse
import os
import sys
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import bonesis
import clingo
from bonesis.asp_encoding import clingo_encode
from utils import (
    add_bonesis_arguments,
    apply_bonesis_mode,
    get_node_sets,
    initialize_bonesis,
    next_solution,
    print_clingo_optimization,
    print_node_reference,
    ptqdm,
)

from scbolt import cli, console
from scbolt.runtime import (
    SolverDeadline,
    SolverPatience,
    SolverPatienceExpired,
    SolverTimeout,
    exit_solver_timeout,
    parse_solver_timeout,
    reset_solver_timeout_status,
)

bonesis.settings["quiet"] = True
script_name = Path(__file__).name
STRUCTURAL_ATOM_ARITIES = {
    "node": 1,
    "clause": 4,
    "constant": 2,
}


def read_gene_list(file: str | Path | None) -> list[str]:
    """Read one gene name per non-empty line."""

    if file is None:
        return []
    with open(file) as stream:
        return [line.rstrip() for line in stream if line.rstrip()]


def make_filter_nodes_score_formatter(
    important_total: int,
    node_total: int,
) -> Callable[[Sequence[int]], Mapping[str, str]]:
    """Create the progress score formatter used during node selection."""

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
    """Create the progress score formatter used during constant selection."""

    def format_score(score: Sequence[int]) -> Mapping[str, str]:
        values = [abs(int(value)) for value in score]
        if not values:
            return {"score": str(list(score))}

        removed_nodes = (
            values[-2] if important_total and len(values) >= 2 else values[-1]
        )
        kept_nodes = max(node_total - removed_nodes, 0)
        fields = {"total": f"{kept_nodes}/{node_total}"}
        if important_total and len(values) >= 2:
            fields = {
                "important": f"{values[-1]}/{important_total}",
                **fields,
            }
        return fields

    return format_score


def get_clingo_options(configuration=None, *extra_options):
    """Build raw Clingo options for selection views."""

    options = []
    if configuration:
        options.append(f"--configuration={configuration}")
    options.extend(option for option in extra_options if option)
    return options


def get_filter_clingo_options(
    mode,
    strategy,
    configuration=None,
    *extra_options,
):
    """Build optimization options for a selection view."""

    options = get_clingo_options(configuration)
    if mode == "opt":
        options.extend(["--opt-mode=opt", f"--opt-strategy={strategy}"])
    elif mode.startswith("enum,"):
        options.append(f"--opt-mode={mode}")
    elif mode == "ignore":
        options.append("--opt-mode=ignore")
    options.extend(option for option in extra_options if option)
    return options


def get_filter_clingo_settings(
    mode,
    strategy,
    configuration=None,
    *extra_options,
):
    """Return BoNesis settings containing selection-specific Clingo options."""

    options = get_filter_clingo_options(
        mode,
        strategy,
        configuration,
        *extra_options,
    )
    return {"clingo_options": options} if options else {}


def format_node_coverage(name, kept, total):
    """Format retained and removed node counts."""

    removed = total - kept
    pct = 0 if total == 0 else 100 * kept / total
    return f"{name}: kept={kept}/{total} ({pct:.1f}%), removed={removed}"


def print_node_solution(solution, nodes_in_data, nodes_in_domain, **kwargs):
    """Print node-selection coverage against data and domain nodes."""

    solution = set(solution)
    console.print_result(f"solution: nodes={len(solution)}", **kwargs)
    console.print_result(
        format_node_coverage(
            "data",
            len(nodes_in_data & solution),
            len(nodes_in_data),
        ),
        **kwargs,
    )
    console.print_result(
        format_node_coverage(
            "domain",
            len(nodes_in_domain & solution),
            len(nodes_in_domain),
        ),
        **kwargs,
    )


def write_lines(lines: Iterable[str], file: Path) -> None:
    """Atomically write normalized lines to a text file."""

    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(f".{file.name}.tmp")
    with open(temporary, "w") as stream:
        for line in lines:
            stream.write(f"{line}\n")
    os.replace(temporary, file)


def write_node_solution(nodes: Iterable[str], file: Path) -> None:
    """Write one selected node per line."""

    write_lines(nodes, file)


def structural_witness(atoms: Iterable[clingo.Symbol]) -> tuple[str, ...]:
    """Extract the Boolean-network structure needed for a solver warm start."""

    return tuple(
        sorted(
            str(atom)
            for atom in atoms
            if STRUCTURAL_ATOM_ARITIES.get(atom.name) == len(atom.arguments)
        )
    )


def read_structural_witness(file: Path | None) -> tuple[str, ...]:
    """Read and validate a structural witness when one is available."""

    if file is None or not file.is_file():
        return ()

    witness = []
    with open(file) as stream:
        for line_number, line in enumerate(stream, start=1):
            expression = line.strip().removesuffix(".")
            if not expression:
                continue
            try:
                atom = clingo.parse_term(expression)
            except RuntimeError as error:
                raise ValueError(
                    f"invalid structural witness at {file}:{line_number}"
                ) from error
            if STRUCTURAL_ATOM_ARITIES.get(atom.name) != len(atom.arguments):
                raise ValueError(
                    f"unsupported structural witness atom at "
                    f"{file}:{line_number}: {atom}"
                )
            witness.append(str(atom))
    return tuple(sorted(set(witness)))


def write_structural_witness(witness: Iterable[str], file: Path) -> None:
    """Write an executable structural witness as ASP facts."""

    write_lines((f"{atom}." for atom in sorted(set(witness))), file)


def structural_witness_clause_bound(witness: Iterable[str]) -> int:
    """Return the smallest clause bound compatible with a structural witness."""

    bound = 1
    for expression in witness:
        atom = clingo.parse_term(expression)
        if atom.name != "clause":
            continue

        clause_id = atom.arguments[1]
        if clause_id.type != clingo.SymbolType.Number:
            raise ValueError(f"invalid clause identifier in witness atom: {atom}")
        bound = max(bound, clause_id.number)

    return bound


def clause_continuation_bounds(
    max_clause: int,
    lower_bound: int = 1,
) -> tuple[int, ...]:
    """Return increasing clause bounds compatible with the initial witness."""

    if max_clause < 1:
        raise ValueError("`max_clause` must be greater than or equal to 1")
    if lower_bound < 1:
        raise ValueError("`lower_bound` must be greater than or equal to 1")
    if lower_bound > max_clause:
        raise ValueError(
            "initial structural witness requires "
            f"max_clause >= {lower_bound} (got {max_clause})"
        )

    return tuple(range(lower_bound, max_clause + 1))


def make_no_solution_error(
    clause_continuation: bool,
    parameter: str | None = None,
) -> RuntimeError:
    """Create an actionable error for an unsuccessful node selection."""

    opposite = "false" if clause_continuation else "true"
    if parameter is not None:
        suggestion = f"with {parameter}={opposite}"
    elif clause_continuation:
        suggestion = "without --clause-continuation"
    else:
        suggestion = "with --clause-continuation"

    return RuntimeError(f"no solution found (please try {suggestion})")


def fork_bonesis(
    bo: bonesis.BoNesis,
    *,
    max_clause: int,
    witness: Iterable[str] = (),
) -> bonesis.BoNesis:
    """Create an independent BoNesis problem at a new clause bound."""

    domain_options = dict(bo.domain.options)
    domain_options["maxclause"] = max_clause
    domain = bonesis.domains.InfluenceGraph(bo.domain, **domain_options)
    stage = bonesis.BoNesis(domain, bo.data)
    stage.manager.reset_from(bo.manager)

    witness = tuple(witness)
    if witness:
        # BoNesis serializes custom lines as facts and appends a final dot.
        # Clingo directives such as #heuristic must not receive a dot after
        # their weight tuple, so the trailing comment absorbs it.
        for atom in witness:
            stage.custom(f"#heuristic {atom}. [1000@100,true] %")
        stage.custom(
            "#heuristic clause(N,C,L,S) : in(L,N,S), maxC(N,M), C=1..M. "
            "[1@10,false] %"
        )

    return stage


def make_stage_progress(description: str):
    """Create a progress factory with a stage-specific description."""

    def progress(*args, **kwargs):
        kwargs["desc"] = description
        return ptqdm(*args, **kwargs)

    return progress


parser_description = """Select Boolean network components using BoNesis.

Two actions are proposed:
    - filter-nodes:
        component selection maximizing variable number while constraining
        Boolean networks to satisfy the observations
    - filter-consts:
        component selection removing strong constants while constraining
        Boolean networks to satisfy the observations

See Chevalier et al. (2024):
https://hal.science/hal-04629083/document
"""

parser = argparse.ArgumentParser(
    prog="select",
    description=parser_description,
    usage=(
        f"python {script_name} [filter-nodes | filter-consts] " "<FILE> <FILE> [<args>]"
    ),
    formatter_class=cli.HelpFormatter,
)
parser.add_argument(
    "action",
    choices=["filter-nodes", "filter-consts"],
    metavar="[filter-nodes | filter-consts]",
    help="BoNesis gene-selection action to run",
)
add_bonesis_arguments(parser)
parser.add_argument(
    "--important-nodes",
    dest="important_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help=(
        "input file storing important nodes prioritized to appear "
        "(format: json or txt)"
    ),
)
parser.add_argument(
    "--mandatory-nodes",
    dest="mandatory_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help=(
        "input file storing mandatory nodes forced to appear " "(format: json or txt)"
    ),
)
parser.add_argument(
    "--domain-nodes",
    dest="domain_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="optional output storing the full domain node set",
)
parser.add_argument(
    "--clingo-configuration",
    dest="clingo_configuration",
    type=str,
    required=False,
    default=None,
    metavar="[auto | frumpy | jumpy | tweety | handy | crafty | trendy | many | FILE]",
    help=(
        "Clingo default configuration passed as --configuration; if not "
        "specified, BoNesis/Clingo defaults are used"
    ),
)
parser.add_argument(
    "--clingo-opt-strategy",
    dest="clingo_opt_strategy",
    action=cli.Clingo_opt_strategy,
    required=False,
)
parser.add_argument(
    "--clause-continuation",
    dest="clause_continuation",
    action="store_true",
    help=(
        "solve increasing clause bounds and reuse each structural witness "
        "as a soft heuristic"
    ),
)
parser.add_argument(
    "--clause-continuation-patience",
    dest="clause_continuation_patience",
    type=parse_solver_timeout,
    required=False,
    default=0.0,
    metavar="DURATION",
    help=(
        "maximum time without a Clingo objective improvement before "
        "continuing to the next intermediate clause bound; suffixes s, m, "
        "h and d are supported, and 0 disables the patience (default: 0)"
    ),
)
parser.add_argument(
    "--clause-continuation-parameter",
    dest="clause_continuation_parameter",
    type=str,
    required=False,
    default=None,
    help=argparse.SUPPRESS,
)
parser.add_argument(
    "--initial-witness",
    dest="initial_witness",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help=argparse.SUPPRESS,
)
parser.add_argument(
    "--witness",
    dest="witness",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help=argparse.SUPPRESS,
)

args = parser.parse_args()
reset_solver_timeout_status(args.timeout_status_file)
if args.witness is None:
    args.witness = args.solution.with_name("witness.lp")

bo, canonical, clingo_parallel_option = initialize_bonesis(
    args,
    allow_skipping_nodes=args.action == "filter-nodes",
    default_canonical=False,
)
new_constraints = apply_bonesis_mode(bo, args.bonesis_mode)

if args.domain_nodes is not None:
    write_node_solution(bo.domain.nodes, args.domain_nodes)

if args.action == "filter-nodes":
    console.print_task("maximizing satisfiable nodes")

    bo.maximize_nodes()

    mandatory_nodes = read_gene_list(args.mandatory_nodes)
    for node in mandatory_nodes:
        bo.custom(f"node({clingo_encode(node)}).")

    important_nodes = set(read_gene_list(args.important_nodes))
    important_nodes_in_domain = important_nodes & set(bo.domain.nodes)
    for node in important_nodes_in_domain:
        bo.custom(f"important_node({clingo_encode(node)}).")

    bo.custom("#maximize { 1@100,N: important_node(N),node(N) }.")
    filter_nodes_score_formatter = make_filter_nodes_score_formatter(
        important_total=len(important_nodes_in_domain),
        node_total=len(bo.domain.nodes),
    )
    ptqdm.score_formatter = filter_nodes_score_formatter
    ptqdm.initial_postfix = filter_nodes_score_formatter(
        [0, 0] if important_nodes_in_domain else [0]
    )
    nodes_in_data, nodes_in_domain, domain_edges = get_node_sets(bo)
    initial_witness = read_structural_witness(args.initial_witness)

    if not new_constraints:
        console.print_info("no new constraints added; stopping", flush=True)
        write_node_solution(bo.domain.nodes, args.solution)
        if initial_witness:
            write_structural_witness(initial_witness, args.witness)
        sys.exit(0)

    effective_clingo_opt_strategy = args.clingo_opt_strategy or "bb,dec"
    print_node_reference(
        nodes_in_data,
        nodes_in_domain,
        domain_edges,
        flush=True,
    )
    print_clingo_optimization(
        args.clingo_opt_mode,
        effective_clingo_opt_strategy,
        args.max_clause,
        canonical,
        configuration=args.clingo_configuration or "auto",
        jobs=args.jobs,
        flush=True,
    )
    console.print_warning("this may take some time.", flush=True)

    initial_witness_clause_bound = structural_witness_clause_bound(initial_witness)
    if initial_witness_clause_bound > args.max_clause:
        raise ValueError(
            "initial structural witness requires "
            f"max_clause >= {initial_witness_clause_bound} "
            f"(got {args.max_clause})"
        )

    bounds = (
        clause_continuation_bounds(
            args.max_clause,
            lower_bound=initial_witness_clause_bound,
        )
        if args.clause_continuation
        else (args.max_clause,)
    )
    current_witness = initial_witness
    solution = None
    deadline = SolverDeadline(args.timeout)

    for stage_index, max_clause in enumerate(bounds, start=1):
        is_target = max_clause == args.max_clause
        stage_name = "Target optimization" if is_target else "Clause continuation"
        clingo_opt_mode = args.clingo_opt_mode
        clingo_opt_strategy = effective_clingo_opt_strategy
        description = (
            f"{stage_name} [{stage_index}/{len(bounds)}, "
            f"max clauses={max_clause}, mode={clingo_opt_mode}, "
            f"strategy={clingo_opt_strategy}]"
        )

        stage_bo = fork_bonesis(
            bo,
            max_clause=max_clause,
            witness=current_witness,
        )
        stage_patience = SolverPatience(
            args.clause_continuation_patience if not is_target else 0.0
        )
        stage_best = [None]

        def intermediate_solution(model):
            stage_best[0] = model
            stage_patience.reset()
            nodes, witness = model
            write_structural_witness(witness, args.witness)
            write_node_solution(nodes, args.solution)

        extra_clingo_options = [clingo_parallel_option]
        if current_witness:
            extra_clingo_options.insert(0, "--heuristic=Domain")
        view_settings = get_filter_clingo_settings(
            clingo_opt_mode,
            clingo_opt_strategy,
            args.clingo_configuration,
            *extra_clingo_options,
        )

        view = bonesis.NodesView(
            stage_bo,
            mode=clingo_opt_mode,
            extra=structural_witness,
            intermediate_model_cb=intermediate_solution,
            clingo_opt_strategy=clingo_opt_strategy,
            progress=make_stage_progress(description),
            **view_settings,
        )
        if is_target:
            view.standalone(output_filename=args.asp)

        try:
            solution, current_witness = next_solution(
                view,
                deadline,
                stage_patience,
            )
        except SolverTimeout:
            exit_solver_timeout(args.timeout_status_file)
        except SolverPatienceExpired:
            if stage_best[0] is not None:
                solution, current_witness = stage_best[0]
            next_bound = bounds[stage_index]
            console.print_warning(
                "no Clingo objective improvement within the configured "
                f"clause-continuation patience (max clauses={max_clause}); "
                f"continuing with max clauses={next_bound}",
                flush=True,
            )
            continue
        except StopIteration:
            if is_target:
                raise make_no_solution_error(
                    args.clause_continuation,
                    args.clause_continuation_parameter,
                ) from None
            console.print_warning(
                "clause continuation produced no witness "
                f"(max clauses={max_clause}); continuing",
                flush=True,
            )
            continue
        except RuntimeError:
            if not is_target:
                raise
            if not args.solution.exists() or args.solution.stat().st_size == 0:
                raise
            with open(args.solution) as stream:
                solution = [line.rstrip() for line in stream if line.rstrip()]
            current_witness = read_structural_witness(args.witness)
            if not solution or not current_witness:
                raise
            console.print_debug(
                "selecting intermediate solution "
                "(reason=final model parsing failed, "
                "certification=partial/non-certified)",
                flush=True,
            )

        write_structural_witness(current_witness, args.witness)
        write_node_solution(solution, args.solution)

    if solution is None:
        raise make_no_solution_error(
            args.clause_continuation,
            args.clause_continuation_parameter,
        )

    print_node_solution(
        solution,
        nodes_in_data,
        nodes_in_domain,
        flush=True,
    )

elif args.action == "filter-consts":
    console.print_task("maximizing strong constants")

    bo.maximize_strong_constants()
    if args.minimize_self_loops:
        bo.custom(
            "edge(A,A) :- clause(A,_,A,_). " "#minimize { 1@10000,A: edge(A,A) }."
        )

    important_nodes = set(read_gene_list(args.important_nodes))
    important_nodes_in_domain = important_nodes & set(bo.domain.nodes)
    for node in important_nodes_in_domain:
        bo.custom(f"important_node({clingo_encode(node)}).")

    if important_nodes_in_domain:
        bo.custom(
            "#maximize { 1@1,N: important_node(N), node(N), "
            "not strong_constant(N) }."
        )

    def intermediate_solution(model):
        nodes, witness = model
        write_structural_witness(witness, args.witness)
        write_node_solution(nodes, args.solution)

    clingo_opt_strategy = "usc"
    ptqdm.score_formatter = make_filter_consts_score_formatter(
        node_total=len(bo.domain.nodes),
        important_total=len(important_nodes_in_domain),
    )
    ptqdm.initial_postfix = {"total": f"0/{len(bo.domain.nodes)}"}
    if important_nodes_in_domain:
        ptqdm.initial_postfix = {
            "important": f"0/{len(important_nodes_in_domain)}",
            **ptqdm.initial_postfix,
        }
    view = bonesis.NonStrongConstantNodesView(
        bo,
        mode=args.clingo_opt_mode,
        extra=structural_witness,
        intermediate_model_cb=intermediate_solution,
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
        canonical,
        configuration=args.clingo_configuration or "auto",
        jobs=args.jobs,
    )
    console.print_warning("this may take some time.")
    deadline = SolverDeadline(args.timeout)
    try:
        solution, witness = next_solution(view, deadline)
    except SolverTimeout:
        exit_solver_timeout(args.timeout_status_file)

    write_structural_witness(witness, args.witness)
    write_node_solution(solution, args.solution)

    if important_nodes_in_domain:
        console.print_result(
            "important nodes: "
            f"kept={len(set(solution) & important_nodes_in_domain)}/"
            f"{len(important_nodes_in_domain)}"
        )
    print_node_solution(solution, nodes_in_data, nodes_in_domain)
