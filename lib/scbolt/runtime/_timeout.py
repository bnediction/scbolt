"""Internal solver-deadline utilities shared by inference scripts."""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Generator, Iterator, Literal, NoReturn, Optional

_DURATION_PATTERN = re.compile(
    r"^(?P<value>(?:\d+(?:\.\d*)?|\.\d+))(?P<unit>[smhd]?)$"
)
_DURATION_UNITS = {
    "": 1.0,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
}

CLASP_PROGRAM_NODE_LIMIT = (1 << 28) - 1
_CLASP_PROGRAM_NODE_LIMIT_ERROR = (
    "Value too large for defined data type: Id out of range"
)


class SolverTimeout(TimeoutError):
    """Signal that the configured global solver deadline was reached."""


class SolverPatienceExpired(TimeoutError):
    """Signal that no solver improvement occurred within the patience."""


class SolverCapacityError(RuntimeError):
    """Signal that an ASP program exceeded the solver representation limit."""


class SolverDeadline:
    """Track one monotonic deadline shared by successive solver views."""

    def __init__(self, timeout: float = 0.0) -> None:
        self._expires_at = time.monotonic() + timeout if timeout > 0 else None

    def remaining(self) -> Optional[float]:
        """Return remaining seconds, or None when no deadline is configured."""

        if self._expires_at is None:
            return None
        return max(self._expires_at - time.monotonic(), 0.0)


class SolverPatience:
    """Track a resettable deadline since the latest solver improvement."""

    def __init__(self, patience: float = 0.0) -> None:
        self._duration = patience if patience > 0 else None
        self._lock = Lock()
        self._claimed = False
        self._expires_at = (
            time.monotonic() + patience if self._duration is not None else None
        )

    def reset(self) -> None:
        """Restart the patience after a solver objective improvement."""

        if self._duration is None:
            return
        with self._lock:
            if self._claimed:
                return
            self._expires_at = time.monotonic() + self._duration

    def remaining(self) -> Optional[float]:
        """Return remaining seconds, or None when patience is disabled."""

        with self._lock:
            if self._expires_at is None:
                return None
            return max(self._expires_at - time.monotonic(), 0.0)

    def _claim_expiry(self) -> bool:
        """Atomically claim an elapsed patience unless it was just reset."""

        with self._lock:
            if self._expires_at is None or self._expires_at > time.monotonic():
                return False
            self._claimed = True
            return True


def parse_solver_timeout(value: str) -> float:
    """Parse a non-negative solver duration expressed in seconds to days."""

    match = _DURATION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise argparse.ArgumentTypeError(
            "invalid timeout duration "
            f"(got {value!r}, expected a number followed by s, m, h or d)"
        )

    timeout = float(match.group("value"))
    return timeout * _DURATION_UNITS[match.group("unit")]


def format_duration(seconds: float) -> str:
    """Format a non-negative duration using compact day-to-second units."""

    if seconds < 0:
        raise ValueError("duration must be non-negative")
    if not float(seconds).is_integer():
        return f"{seconds:g}s"

    seconds = int(seconds)
    days, seconds = divmod(seconds, 24 * 60 * 60)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)

    if days:
        if seconds:
            return f"{days}d{hours:02d}h{minutes:02d}m{seconds:02d}s"
        if minutes:
            return f"{days}d{hours:02d}h{minutes:02d}m"
        if hours:
            return f"{days}d{hours:02d}h"
        return f"{days}d"
    if hours:
        if seconds:
            return f"{hours}h{minutes:02d}m{seconds:02d}s"
        if minutes:
            return f"{hours}h{minutes:02d}m"
        return f"{hours}h"
    if minutes:
        if seconds:
            return f"{minutes}m{seconds:02d}s"
        return f"{minutes}m"
    return f"{seconds}s"


def reset_solver_timeout_status(file: Optional[Path]) -> None:
    """Remove a stale solver-timeout status marker when one is configured."""

    if file is not None:
        file.unlink(missing_ok=True)


def exit_solver_timeout(file: Optional[Path]) -> NoReturn:
    """Report a solver timeout to the caller without exposing a process error."""

    _exit_solver_status(file, 124)


def exit_solver_capacity(file: Optional[Path]) -> NoReturn:
    """Report a solver capacity stop without exposing a process traceback."""

    _exit_solver_status(file, 125)


def _exit_solver_status(file: Optional[Path], status: int) -> NoReturn:
    """Persist one solver exit status for the surrounding runtime wrapper."""

    if file is None:
        sys.exit(status)

    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(f".{file.name}.tmp")
    temporary.write_text(f"{status}\n")
    os.replace(temporary, file)
    sys.exit(0)


_SolverStopReason = Literal["timeout", "patience"]


def _next_solver_stop(
    deadline: Optional[SolverDeadline],
    patience: Optional[SolverPatience],
) -> tuple[Optional[float], Optional[_SolverStopReason]]:
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
    error: Optional[BaseException] = None,
) -> NoReturn:
    """Raise the exception corresponding to a solver stop reason."""

    if reason == "timeout":
        raise SolverTimeout from error
    raise SolverPatienceExpired from error


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


def _claim_solver_stop(
    deadline: Optional[SolverDeadline],
    patience: Optional[SolverPatience],
) -> Optional[_SolverStopReason]:
    """Atomically select an elapsed stop condition, prioritizing timeout."""

    if deadline is not None:
        remaining = deadline.remaining()
        if remaining is not None and remaining <= 0:
            return "timeout"
    if patience is not None and patience._claim_expiry():
        return "patience"
    return None


def iter_solutions(
    view: Any,
    deadline: Optional[SolverDeadline] = None,
    patience: Optional[SolverPatience] = None,
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
    stop_reason: Optional[_SolverStopReason] = None
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

    def raise_if_stopped(error: Optional[BaseException] = None) -> None:
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
