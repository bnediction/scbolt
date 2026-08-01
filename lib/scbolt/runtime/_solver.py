"""Solver lifecycle controls shared by scBOLT inference scripts."""

import os
import sys
from collections.abc import Generator, Iterator
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Literal, NoReturn

from ._timeout import (
    SolverDeadline,
    SolverPatience,
    SolverPatienceExpired,
    SolverTimeout,
)

CLASP_PROGRAM_NODE_LIMIT = (1 << 28) - 1
_CLASP_PROGRAM_NODE_LIMIT_ERROR = (
    "Value too large for defined data type: Id out of range"
)
_SolverStopReason = Literal["timeout", "patience"]


class SolverCapacityError(RuntimeError):
    """Signal that an ASP program exceeded the solver representation limit."""


def reset_solver_timeout_status(file: Path | None) -> None:
    """Remove a stale solver-timeout status marker when one is configured."""

    if file is not None:
        file.unlink(missing_ok=True)


def exit_solver_timeout(file: Path | None) -> NoReturn:
    """Report a solver timeout to the caller without exposing a process error."""

    _exit_solver_status(file, 124)


def exit_solver_capacity(file: Path | None) -> NoReturn:
    """Report a solver capacity stop without exposing a process traceback."""

    _exit_solver_status(file, 125)


def interrupt_solver_view(
    view: Any,
    *,
    cancel_handler: bool = True,
) -> None:
    """Interrupt a solver view and optionally cancel its solve handle."""

    try:
        view.interrupt()
    except (AttributeError, RuntimeError):
        pass

    if not cancel_handler:
        return

    solve_handler = getattr(view, "_solve_handler", None)
    if solve_handler is not None:
        try:
            solve_handler.cancel()
        except (AttributeError, RuntimeError):
            pass


def iter_solver_view(view: Any) -> Iterator[Any]:
    """Initialize a solver view and normalize known capacity failures."""

    try:
        return iter(view)
    except RuntimeError as error:
        if _CLASP_PROGRAM_NODE_LIMIT_ERROR not in str(error):
            raise
        raise SolverCapacityError(
            "ASP grounding exceeded Clasp's internal program-node limit "
            f"({CLASP_PROGRAM_NODE_LIMIT:,})"
        ) from error


def iter_solutions(
    view: Any,
    deadline: SolverDeadline | None = None,
    patience: SolverPatience | None = None,
) -> Generator[Any, None, None]:
    """Iterate until completion, the global deadline, or patience expiry."""

    iterator = iter_solver_view(view)
    remaining, _ = _next_solver_stop(deadline, patience)
    if remaining is None:
        while True:
            try:
                solution = next(iterator)
            except StopIteration:
                return
            yield solution

    stopped = Event()
    finished = Event()
    state_lock = Lock()
    stop_reason: _SolverStopReason | None = None
    active = True

    def interrupt(reason: _SolverStopReason) -> None:
        nonlocal active, stop_reason

        with state_lock:
            if not active:
                return
            stop_reason = reason
            stopped.set()

        interrupt_solver_view(view)

    if remaining is not None and remaining <= 0:
        initial_reason = _claim_solver_stop(deadline, patience)
        if initial_reason is None:
            raise RuntimeError("expired solver deadline has no stop reason")
        interrupt(initial_reason)
        _raise_solver_stop(initial_reason)

    def watch() -> None:
        while not finished.is_set():
            remaining, reason = _next_solver_stop(deadline, patience)
            if remaining is None or reason is None:
                return
            if remaining > 0 and finished.wait(remaining):
                return

            reason = _claim_solver_stop(deadline, patience)
            if reason is None:
                continue
            interrupt(reason)
            return

    def raise_if_stopped(error: BaseException | None = None) -> None:
        if not stopped.is_set():
            return
        with state_lock:
            reason = stop_reason
        if reason is None:
            raise RuntimeError("solver stopped without a reason") from error
        _raise_solver_stop(reason, error)

    watchdog = Thread(target=watch, name="scbolt-solver-watchdog", daemon=True)
    watchdog.start()

    try:
        while True:
            try:
                solution = next(iterator)
            except StopIteration:
                raise_if_stopped()
                return
            except RuntimeError as error:
                raise_if_stopped(error)
                raise

            raise_if_stopped()
            yield solution
    finally:
        with state_lock:
            active = False
        finished.set()
        watchdog.join()


def close_solver_progress(view: Any) -> None:
    """Close and clear a solver view progress bar when present."""

    progressbar = getattr(view, "_progressbar", None)
    if progressbar is not None:
        progressbar.leave = False
        progressbar.clear()
        progressbar.close()


def next_solution(
    view: Any,
    deadline: SolverDeadline | None = None,
    patience: SolverPatience | None = None,
) -> Any:
    """Return the next view solution and clear its progress bar."""

    solutions = iter_solutions(view, deadline, patience)
    try:
        return next(solutions)
    finally:
        try:
            solutions.close()
        finally:
            close_solver_progress(view)


def _exit_solver_status(file: Path | None, status: int) -> NoReturn:
    """Persist one solver exit status for the surrounding runtime wrapper."""

    if file is None:
        sys.exit(status)

    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(f".{file.name}.tmp")
    temporary.write_text(f"{status}\n")
    os.replace(temporary, file)
    sys.exit(0)


def _next_solver_stop(
    deadline: SolverDeadline | None,
    patience: SolverPatience | None,
) -> tuple[float | None, _SolverStopReason | None]:
    """Return the nearest active solver deadline and its reason."""

    timeout_remaining = deadline.remaining() if deadline is not None else None
    patience_remaining = patience.remaining() if patience is not None else None

    if timeout_remaining is not None and timeout_remaining <= 0:
        return 0.0, "timeout"
    if patience_remaining is not None and patience_remaining <= 0:
        return 0.0, "patience"
    if timeout_remaining is None:
        return patience_remaining, (
            "patience" if patience_remaining is not None else None
        )
    if patience_remaining is None or timeout_remaining <= patience_remaining:
        return timeout_remaining, "timeout"
    return patience_remaining, "patience"


def _raise_solver_stop(
    reason: _SolverStopReason,
    error: BaseException | None = None,
) -> NoReturn:
    """Raise the exception corresponding to a solver stop reason."""

    if reason == "timeout":
        raise SolverTimeout from error
    raise SolverPatienceExpired from error


def _claim_solver_stop(
    deadline: SolverDeadline | None,
    patience: SolverPatience | None,
) -> _SolverStopReason | None:
    """Atomically select an elapsed stop condition, prioritizing timeout."""

    if deadline is not None:
        remaining = deadline.remaining()
        if remaining is not None and remaining <= 0:
            return "timeout"
    if patience is not None and patience._claim_expiry():
        return "patience"
    return None
