import argparse
import os
import sys
from functools import partial
from pathlib import Path

import bonesis
from bonesis.asp_encoding import clingo_encode
from scbolt import cli, console
from scbolt.inference import should_forward_previous_solution
from scbolt.inference._continuation import (
    DomainMemoryEstimator,
    clause_continuation_bounds,
    continuation_base_domain,
    solution_reaches_domain_ceiling,
    stalled_domain_solver_settings,
)
from scbolt.inference._portfolio import (
    DOMAIN_MEMORY_COST_FACTOR,
    DOMAIN_MEMORY_LAUNCH_INTERVAL_SECONDS,
    DOMAIN_MEMORY_PROBE_SECONDS,
    continue_domain_at_clause_bound,
)
from scbolt.inference._selection import (
    format_progress_ratio,
    fork_bonesis,
    get_filter_clingo_settings,
    make_filter_consts_score_formatter,
    make_filter_nodes_score_formatter,
    make_no_solution_error,
    make_solver_capacity_error,
    make_stage_progress,
    print_clause_bound_patience_warning,
    print_node_solution,
    ptqdm,
    retain_intermediate_node_solution,
    store_retained_model,
    write_intermediate_solution,
    write_lines,
    write_node_solution,
)
from scbolt.inference._witness import (
    read_structural_witness,
    structural_witness,
    structural_witness_clause_bound,
    structural_witness_nodes,
    write_structural_witness,
)
from scbolt.runtime import (
    SolverCapacityError,
    SolverDeadline,
    SolverPatience,
    SolverPatienceExpired,
    SolverTimeout,
    exit_solver_capacity,
    exit_solver_timeout,
    format_duration,
    format_memory_size,
    next_solution,
    parse_memory_limit,
    parse_solver_timeout,
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


def parse_min_domain_yield(value: str) -> float:
    """Parse a half-open unit-interval domain-yield threshold."""

    try:
        minimum_yield = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "expected a numeric value greater than or equal to 0 and below 1"
        ) from error
    if not 0 <= minimum_yield < 1:
        raise argparse.ArgumentTypeError(
            "expected a value greater than or equal to 0 and below 1"
        )
    return minimum_yield


def read_gene_list(file: str | Path | None) -> list[str]:
    """Read one gene name per non-empty line."""

    if file is None:
        return []
    with open(file) as stream:
        return [line.rstrip() for line in stream if line.rstrip()]



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


def main() -> None:
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
        "--forbidden-nodes",
        dest="forbidden_nodes",
        type=lambda x: Path(x).resolve(),
        required=False,
        default=None,
        metavar="FILE",
        help="input file storing nodes excluded from the regulatory domain",
    )
    parser.add_argument(
        "--domain-size-file",
        dest="domain_size_file",
        type=lambda x: Path(x).resolve(),
        required=False,
        default=None,
        metavar="FILE",
        help="optional output storing the full domain size",
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
        "--clingo-strategy",
        dest="clingo_strategy",
        action=cli.Clingo_strategy,
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
        "--clause-bound-patience",
        dest="clause_bound_patience",
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
        "--domain-continuation",
        dest="domain_continuation",
        action="store_true",
        help=(
            "search candidate regulatory subdomains in parallel and expand "
            "the selected witness toward the complete domain"
        ),
    )
    parser.add_argument(
        "--domain-continuation-expansion-only",
        dest="domain_continuation_expansion_only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--domain-wave-patience",
        dest="domain_wave_patience",
        type=parse_solver_timeout,
        required=False,
        default=0.0,
        metavar="DURATION",
        help=(
            "full stagnation time after improving the best objective within one "
            "domain-continuation wave; a candidate entering solving or first "
            "reaching the best objective guarantees at least 40%% of the "
            "configured patience remains; suffixes s, m, h "
            "and d are supported, and 0 disables the patience (default: 0)"
        ),
    )
    parser.add_argument(
        "--min-domain-yield",
        dest="min_domain_yield",
        type=parse_min_domain_yield,
        required=False,
        default=0.10,
        metavar="FLOAT",
        help=(
            "minimum cumulative retained-node gain per node added during domain "
            "expansion; low-yield expansions are refreshed at constant size, "
            "and 0 disables refreshes (default: 0.10)"
        ),
    )
    parser.add_argument(
        "--max-domain-refreshes",
        dest="max_domain_refreshes",
        type=int,
        required=False,
        default=1,
        metavar="INT",
        help=(
            "maximum number of constant-size domain refreshes per domain size; "
            "0 disables domain refreshes (default: 1)"
        ),
    )
    parser.add_argument(
        "--domain-continuation-jobs",
        dest="domain_continuation_jobs",
        type=int,
        required=False,
        default=1,
        metavar="INT",
        help=(
            "maximum independent domain-continuation workers "
            "(default: 1)"
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
            "soft process-memory limit used to schedule domain candidates; "
            "integers are interpreted as GB"
        ),
    )
    parser.add_argument(
        "--domain-continuation-seed",
        dest="domain_continuation_seed",
        type=int,
        required=False,
        default=int(os.getenv("PYTHONHASHSEED", "0")),
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
        "--forward-witness",
        dest="forward_witness",
        type=lambda x: Path(x).resolve(),
        required=False,
        default=None,
        metavar="FILE",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--forwarded-status-file",
        dest="forwarded_status_file",
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
    if args.domain_continuation_jobs < 1:
        parser.error("--domain-continuation-jobs must be greater than or equal to 1")
    if args.max_domain_refreshes < 0:
        parser.error("--max-domain-refreshes must be greater than or equal to 0")
    if args.domain_continuation and args.action != "filter-nodes":
        parser.error("--domain-continuation is only available with filter-nodes")
    if args.domain_continuation_expansion_only and not args.domain_continuation:
        parser.error(
            "--domain-continuation-expansion-only requires "
            "--domain-continuation"
        )
    if args.domain_continuation_expansion_only and args.initial_witness is None:
        parser.error(
            "--domain-continuation-expansion-only requires --initial-witness"
        )
    if args.initial_witness is not None and args.forward_witness is not None:
        parser.error("--initial-witness and --forward-witness are mutually exclusive")
    reset_solver_timeout_status(args.timeout_status_file)
    if args.forwarded_status_file is not None:
        args.forwarded_status_file.unlink(missing_ok=True)
    if args.witness is None:
        args.witness = args.solution.with_name("witness.lp")

    bo, canonical, clingo_parallel_option = initialize_bonesis(
        args,
        allow_skipping_nodes=args.action == "filter-nodes",
        default_canonical=False,
        forbidden_nodes_file=args.forbidden_nodes,
    )
    new_constraints = apply_bonesis_mode(bo, args.bonesis_mode)

    if args.domain_size_file is not None:
        write_lines((str(len(bo.domain.nodes)),), args.domain_size_file)

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

        if should_forward_previous_solution(new_constraints, initial_witness):
            forwarded_nodes = (
                read_gene_list(args.filter_grn)
                if args.filter_grn is not None
                else sorted(bo.domain.nodes)
            )
            forwarded_witness = read_structural_witness(args.forward_witness)
            console.print_info(
                "no new constraints added; forwarding previous solution",
                flush=True,
            )
            write_node_solution(forwarded_nodes, args.solution)
            write_structural_witness(forwarded_witness, args.witness)
            if args.forwarded_status_file is not None:
                write_lines(("forwarded",), args.forwarded_status_file)
            sys.exit(0)

        if args.domain_continuation_expansion_only and not initial_witness:
            parser.error(
                "--domain-continuation-expansion-only requires a non-empty "
                "structural witness"
            )

        effective_clingo_strategy = args.clingo_strategy or "bb,dec"
        console.print_node_reference(
            nodes_in_data,
            nodes_in_domain,
            domain_edges,
            flush=True,
        )
        console.print_solver_options(
            args.clingo_mode,
            effective_clingo_strategy,
            args.max_clauses,
            canonical,
            configuration=args.clingo_configuration or "auto",
            jobs=args.jobs,
            flush=True,
        )
        initial_witness_clause_bound = structural_witness_clause_bound(initial_witness)
        if initial_witness_clause_bound > args.max_clauses:
            raise ValueError(
                "initial structural witness requires "
                f"max_clauses >= {initial_witness_clause_bound} "
                f"(got {args.max_clauses})"
            )

        bounds = (
            clause_continuation_bounds(
                args.max_clauses,
                lower_bound=initial_witness_clause_bound,
            )
            if args.clause_continuation
            else (args.max_clauses,)
        )
        if args.clause_continuation:
            bounds_text = (
                str(bounds[0])
                if len(bounds) == 1
                else f"{bounds[0]}..{bounds[-1]}"
            )
            console.print_options(
                "clause continuation: "
                f"bounds={bounds_text}, "
                "bound patience="
                f"{format_duration(args.clause_bound_patience)}",
                flush=True,
            )
        else:
            console.print_options("clause continuation: none", flush=True)

        if args.domain_continuation:
            continuation_mode = (
                "expansion"
                if args.domain_continuation_expansion_only
                else "adaptive"
            )
            console.print_options(
                "domain continuation: "
                f"mode={continuation_mode}, "
                "patience="
                f"{format_duration(args.domain_wave_patience)}, "
                f"yield={args.min_domain_yield:.1%}, "
                f"refreshes={args.max_domain_refreshes}",
                flush=True,
            )
            if args.memory_limit is not None:
                console.print_options(
                    "domain memory: "
                    f"limit={format_memory_size(args.memory_limit)}, "
                    f"probe={DOMAIN_MEMORY_PROBE_SECONDS:g}s, "
                    "launch interval="
                    f"{DOMAIN_MEMORY_LAUNCH_INTERVAL_SECONDS:g}s, "
                    "candidate margin="
                    f"{DOMAIN_MEMORY_COST_FACTOR - 1:.0%}",
                    flush=True,
                )
        else:
            console.print_options("domain continuation: none", flush=True)
        console.print_warning("this may take some time.", flush=True)
        complete_domain = frozenset(bo.domain.nodes)
        required_nodes = (
            set(mandatory_nodes) | important_nodes_in_domain
        ) & complete_domain
        initial_solution = structural_witness_nodes(initial_witness)
        current_witness = initial_witness
        current_domain = (
            continuation_base_domain(
                initial_solution,
                required_nodes,
                complete_domain,
            )
            if args.domain_continuation
            else complete_domain
        )
        solution = tuple(initial_solution)
        retained = {
            "domain": current_domain,
            "solution": solution,
            "witness": current_witness,
            "objective": (
                len(set(solution) & important_nodes_in_domain),
                len(solution),
            ),
        }
        if current_witness:
            write_node_solution(solution, args.solution)
            write_structural_witness(current_witness, args.witness)

        deadline = SolverDeadline(args.timeout)
        domain_memory_estimator = (
            DomainMemoryEstimator()
            if args.domain_continuation and args.memory_limit is not None
            else None
        )

        for stage_index, max_clause in enumerate(bounds, start=1):
            if stage_index > 1:
                current_domain = (
                    continuation_base_domain(
                        solution,
                        required_nodes,
                        complete_domain,
                    )
                    if args.domain_continuation
                    else complete_domain
                )
                retained["domain"] = current_domain

            is_target = max_clause == args.max_clauses
            stage_name = "Target optimization" if is_target else "Clause continuation"
            clingo_mode = args.clingo_mode
            clingo_strategy = effective_clingo_strategy
            description = (
                f"{stage_name} [{stage_index}/{len(bounds)}, "
                f"max clauses={max_clause}]"
            )

            stage_patience_seconds = (
                0.0 if is_target else args.clause_bound_patience
            )
            stage_patience = SolverPatience(stage_patience_seconds)
            stage_best = [None]
            complete_domain_optimal = False
            terminal_refinement_used = False
            direct_target_optimization = False
            retain_model = partial(
                store_retained_model,
                retained,
                important_nodes=important_nodes_in_domain,
                witness_file=args.witness,
                solution_file=args.solution,
            )
            retain_selected = partial(retain_model, force=True)

            if args.domain_continuation:
                continuation = None
                domain_clingo_mode = clingo_mode
                domain_clingo_strategy = clingo_strategy
                while continuation is None:
                    try:
                        continuation = continue_domain_at_clause_bound(
                            bo,
                            max_clause=max_clause,
                            initial_domain=current_domain,
                            initial_solution=solution,
                            initial_witness=current_witness,
                            expansion_only=args.domain_continuation_expansion_only,
                            required_nodes=required_nodes,
                            important_nodes=important_nodes_in_domain,
                            jobs=args.domain_continuation_jobs,
                            seed=args.domain_continuation_seed,
                            clingo_mode=domain_clingo_mode,
                            clingo_strategy=domain_clingo_strategy,
                            clingo_configuration=args.clingo_configuration,
                            domain_patience_seconds=args.domain_wave_patience,
                            minimum_domain_yield=args.min_domain_yield,
                            max_domain_refreshes=args.max_domain_refreshes,
                            clause_patience=stage_patience,
                            deadline=deadline,
                            memory_limit=args.memory_limit,
                            on_model=retain_model,
                            on_selected=retain_selected,
                            memory_estimator=domain_memory_estimator,
                        )
                    except SolverTimeout:
                        exit_solver_timeout(args.timeout_status_file)
                    except SolverPatienceExpired:
                        solution = tuple(retained["solution"])
                        current_witness = tuple(retained["witness"])
                        current_domain = frozenset(retained["domain"])
                        print_clause_bound_patience_warning(
                            max_clause,
                            retained["objective"],
                            node_total=len(current_domain),
                            important_total=len(important_nodes_in_domain),
                            patience=args.clause_bound_patience,
                        )
                        fallback_settings = stalled_domain_solver_settings(
                            domain_clingo_mode,
                            domain_clingo_strategy,
                        )
                        if (
                            fallback_settings is None
                            or not solution
                            or not current_witness
                        ):
                            break
                        domain_clingo_mode, domain_clingo_strategy = (
                            fallback_settings
                        )
                        terminal_refinement_used = True
                        stage_patience = SolverPatience(stage_patience_seconds)
                        console.print_info(
                            "switching domain continuation solver "
                            f"(max clauses={max_clause}, "
                            f"mode={domain_clingo_mode}, "
                            f"strategy={domain_clingo_strategy}, "
                            f"domain={len(current_domain)})",
                            flush=True,
                        )
                    except SolverCapacityError as error:
                        capacity_error = make_solver_capacity_error(
                            error,
                            domain_continuation=True,
                            clause_continuation_parameter=(
                                args.clause_continuation_parameter
                            ),
                        )
                        console.print_warning(str(capacity_error), flush=True)
                        exit_solver_capacity(args.timeout_status_file)

                if continuation is None:
                    continue

                if continuation.complete_domain_unsat:
                    if is_target:
                        raise make_no_solution_error(
                            args.clause_continuation,
                            args.clause_continuation_parameter,
                        )
                    solution = tuple(retained["solution"])
                    current_witness = tuple(retained["witness"])
                    console.print_warning(
                        "domain continuation proved the complete domain "
                        f"unsatisfiable (max clauses={max_clause}); continuing",
                        flush=True,
                    )
                    continue

                current_domain = continuation.domain
                solution = continuation.solution
                current_witness = continuation.witness
                complete_domain_optimal = continuation.complete_domain_optimal
                terminal_refinement_used = (
                    terminal_refinement_used
                    or continuation.terminal_refinement_used
                    or continuation.bb_lin_fallback_used
                )
                if continuation.continuation_exhausted:
                    message = (
                        "domain continuation remained unresolved at its "
                        f"minimum boundary (max clauses={max_clause}, "
                        f"domain={len(current_domain)})"
                    )
                    if not is_target:
                        console.print_warning(
                            f"{message}; advancing clause bound",
                            flush=True,
                        )
                        continue
                    console.print_warning(
                        f"{message}; falling back to complete-domain "
                        "target optimization",
                        flush=True,
                    )
                    direct_target_optimization = True
            if solution and current_witness:
                retain_model(current_domain, solution, current_witness)

            stage_clingo_mode, stage_clingo_strategy = (
                ("opt", "bb,lin")
                if terminal_refinement_used
                else (clingo_mode, clingo_strategy)
            )
            objective_ceiling_reached = solution_reaches_domain_ceiling(
                solution,
                complete_domain,
                important_nodes_in_domain,
            )
            if objective_ceiling_reached:
                console.print_debug(
                    "complete-domain objective ceiling reached; "
                    "stopping clause continuation",
                    flush=True,
                )
            elif complete_domain_optimal:
                console.print_debug(
                    "complete-domain optimum certified by domain portfolio",
                    flush=True,
                )

            stage_bo = fork_bonesis(
                bo,
                max_clause=max_clause,
                witness=current_witness,
            )
            intermediate_solution = partial(
                retain_intermediate_node_solution,
                stage_best=stage_best,
                retain_model=retain_model,
                complete_domain=complete_domain,
                stage_patience=stage_patience,
            )

            extra_clingo_options = [clingo_parallel_option]
            if current_witness:
                extra_clingo_options.insert(0, "--heuristic=Domain")
            view_settings = get_filter_clingo_settings(
                stage_clingo_mode,
                stage_clingo_strategy,
                args.clingo_configuration,
                *extra_clingo_options,
            )

            view = bonesis.NodesView(
                stage_bo,
                mode=stage_clingo_mode,
                extra=structural_witness,
                intermediate_model_cb=intermediate_solution,
                clingo_opt_strategy=stage_clingo_strategy,
                progress=make_stage_progress(
                    description,
                    retained["objective"],
                    filter_nodes_score_formatter,
                    has_important_nodes=bool(important_nodes_in_domain),
                ),
                **view_settings,
            )
            if is_target or objective_ceiling_reached:
                view.standalone(output_filename=args.asp)

            try:
                if not args.domain_continuation or direct_target_optimization:
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
                elif retained["solution"]:
                    solution = tuple(retained["solution"])
                    current_witness = tuple(retained["witness"])
                print_clause_bound_patience_warning(
                    max_clause,
                    retained["objective"],
                    node_total=len(retained["domain"]),
                    important_total=len(important_nodes_in_domain),
                    patience=args.clause_bound_patience,
                )
                continue
            except SolverCapacityError as error:
                capacity_error = make_solver_capacity_error(
                    error,
                    domain_continuation=args.domain_continuation,
                    clause_continuation_parameter=args.clause_continuation_parameter,
                )
                console.print_warning(str(capacity_error), flush=True)
                exit_solver_capacity(args.timeout_status_file)
            except StopIteration:
                if is_target:
                    raise make_no_solution_error(
                        args.clause_continuation,
                        args.clause_continuation_parameter,
                    ) from None
                solution = tuple(retained["solution"])
                current_witness = tuple(retained["witness"])
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

            final_objective = (
                len(set(solution) & important_nodes_in_domain),
                len(solution),
            )
            if final_objective < retained["objective"]:
                solution = tuple(retained["solution"])
                current_witness = tuple(retained["witness"])
                current_domain = frozenset(retained["domain"])
            else:
                retain_model(
                    complete_domain,
                    solution,
                    current_witness,
                    force=True,
                )
                current_domain = complete_domain
            write_structural_witness(current_witness, args.witness)
            write_node_solution(solution, args.solution)
            if solution_reaches_domain_ceiling(
                solution,
                complete_domain,
                important_nodes_in_domain,
            ):
                if not objective_ceiling_reached:
                    console.print_debug(
                        "complete-domain objective ceiling reached; "
                        "stopping clause continuation",
                        flush=True,
                    )
                break

        if not solution:
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

        intermediate_solution = partial(
            write_intermediate_solution,
            witness_file=args.witness,
            solution_file=args.solution,
        )

        clingo_strategy = "usc"
        ptqdm.score_formatter = make_filter_consts_score_formatter(
            node_total=len(bo.domain.nodes),
            important_total=len(important_nodes_in_domain),
        )
        ptqdm.initial_postfix = {
            "total": format_progress_ratio(0, len(bo.domain.nodes)),
        }
        if important_nodes_in_domain:
            ptqdm.initial_postfix = {
                "important": format_progress_ratio(
                    0,
                    len(important_nodes_in_domain),
                ),
                **ptqdm.initial_postfix,
            }
        view = bonesis.NonStrongConstantNodesView(
            bo,
            mode=args.clingo_mode,
            extra=structural_witness,
            intermediate_model_cb=intermediate_solution,
            clingo_opt_strategy=clingo_strategy,
            progress=ptqdm,
            **get_filter_clingo_settings(
                args.clingo_mode,
                clingo_strategy,
                args.clingo_configuration,
                "--opt-usc-shrink=inv",
                clingo_parallel_option,
            ),
        )
        view.standalone(output_filename=args.asp)

        nodes_in_data, nodes_in_domain, domain_edges = get_node_sets(bo)
        console.print_node_reference(nodes_in_data, nodes_in_domain, domain_edges)
        console.print_solver_options(
            args.clingo_mode,
            clingo_strategy,
            args.max_clauses,
            canonical,
            configuration=args.clingo_configuration or "auto",
            jobs=args.jobs,
        )
        console.print_options("clause continuation: none")
        console.print_options("domain continuation: none")
        console.print_warning("this may take some time.")
        deadline = SolverDeadline(args.timeout)
        try:
            solution, witness = next_solution(view, deadline)
        except SolverTimeout:
            exit_solver_timeout(args.timeout_status_file)
        except SolverCapacityError as error:
            capacity_error = make_solver_capacity_error(
                error,
                domain_continuation=False,
                clause_continuation_parameter=None,
                domain_continuation_available=False,
            )
            console.print_warning(str(capacity_error), flush=True)
            exit_solver_capacity(args.timeout_status_file)

        write_structural_witness(witness, args.witness)
        write_node_solution(solution, args.solution)

        if important_nodes_in_domain:
            console.print_result(
                "important nodes: "
                f"kept={len(set(solution) & important_nodes_in_domain)}/"
                f"{len(important_nodes_in_domain)}"
            )
        print_node_solution(solution, nodes_in_data, nodes_in_domain)


if __name__ == "__main__":
    main()
