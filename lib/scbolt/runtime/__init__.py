"""Runtime controls shared by scBOLT scripts."""

from ._memory import release_unused_memory
from ._solver import (
    SolverCapacityError,
    close_solver_progress,
    exit_solver_capacity,
    exit_solver_timeout,
    interrupt_solver_view,
    iter_solutions,
    iter_solver_view,
    next_solution,
    reset_solver_timeout_status,
)
from ._threads import (
    get_clingo_parallel_mode,
    get_subset_minimal_clingo_settings,
    single_thread,
)
from ._timeout import (
    SolverDeadline,
    SolverPatience,
    SolverPatienceExpired,
    SolverTimeout,
    format_duration,
    parse_solver_timeout,
)

__all__ = [
    "SolverCapacityError",
    "SolverDeadline",
    "SolverPatience",
    "SolverPatienceExpired",
    "SolverTimeout",
    "close_solver_progress",
    "exit_solver_capacity",
    "exit_solver_timeout",
    "format_duration",
    "get_clingo_parallel_mode",
    "get_subset_minimal_clingo_settings",
    "interrupt_solver_view",
    "iter_solver_view",
    "iter_solutions",
    "next_solution",
    "parse_solver_timeout",
    "release_unused_memory",
    "reset_solver_timeout_status",
    "single_thread",
]
