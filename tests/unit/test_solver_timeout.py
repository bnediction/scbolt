#!/usr/bin/env python3

import argparse
import sys
import tempfile
import time
from pathlib import Path
from threading import Event, Timer

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from scbolt.runtime import (  # noqa: E402
    SolverDeadline,
    SolverPatience,
    SolverPatienceExpired,
    SolverTimeout,
    exit_solver_timeout,
    iter_solutions,
    parse_solver_timeout,
    reset_solver_timeout_status,
)


class ImmediateView:
    def __iter__(self):
        return iter(("solution",))

    def interrupt(self):
        raise AssertionError("completed view was interrupted")


class BlockingView:
    def __init__(self):
        self.released = Event()
        self.interrupted = False

    def __iter__(self):
        return self

    def __next__(self):
        self.released.wait()
        return "late solution"

    def interrupt(self):
        self.interrupted = True
        self.released.set()


assert parse_solver_timeout("30") == 30.0
assert parse_solver_timeout("30s") == 30.0
assert parse_solver_timeout("1.5m") == 90.0
assert parse_solver_timeout("24h") == 86400.0
assert parse_solver_timeout("2d") == 172800.0
assert parse_solver_timeout("0") == 0.0

try:
    parse_solver_timeout("1h30m")
except argparse.ArgumentTypeError:
    pass
else:
    raise AssertionError("composite timeout duration was accepted")

solutions = iter_solutions(ImmediateView(), SolverDeadline(1.0))
try:
    assert next(solutions) == "solution"
finally:
    solutions.close()

view = BlockingView()
started = time.monotonic()
try:
    next(iter_solutions(view, SolverDeadline(0.05)))
except SolverTimeout:
    pass
else:
    raise AssertionError("deadline did not interrupt the view")
elapsed = time.monotonic() - started
assert view.interrupted
assert 0.03 <= elapsed < 1.0, elapsed

view = BlockingView()
started = time.monotonic()
try:
    next(iter_solutions(view, patience=SolverPatience(0.05)))
except SolverPatienceExpired:
    pass
else:
    raise AssertionError("patience did not interrupt the view")
elapsed = time.monotonic() - started
assert view.interrupted
assert 0.03 <= elapsed < 1.0, elapsed

view = BlockingView()
patience = SolverPatience(0.05)
reset = Timer(0.03, patience.reset)
reset.start()
started = time.monotonic()
try:
    next(iter_solutions(view, patience=patience))
except SolverPatienceExpired:
    pass
else:
    raise AssertionError("reset patience did not interrupt the view")
finally:
    reset.join()
elapsed = time.monotonic() - started
assert view.interrupted
assert 0.06 <= elapsed < 1.0, elapsed

view = BlockingView()
started = time.monotonic()
try:
    next(
        iter_solutions(
            view,
            deadline=SolverDeadline(0.04),
            patience=SolverPatience(0.2),
        )
    )
except SolverTimeout:
    pass
else:
    raise AssertionError("global deadline did not take priority")
elapsed = time.monotonic() - started
assert view.interrupted
assert 0.02 <= elapsed < 1.0, elapsed

expired_deadline = SolverDeadline(0.001)
time.sleep(0.01)
view = BlockingView()
try:
    next(iter_solutions(view, expired_deadline))
except SolverTimeout:
    pass
else:
    raise AssertionError("expired deadline yielded a solution")
assert view.interrupted

expired_deadline = SolverDeadline(0.001)
expired_patience = SolverPatience(0.001)
time.sleep(0.01)
view = BlockingView()
try:
    next(iter_solutions(view, expired_deadline, expired_patience))
except SolverTimeout:
    pass
else:
    raise AssertionError("global deadline did not win simultaneous expiry")
assert view.interrupted

with tempfile.TemporaryDirectory() as directory:
    status_file = Path(directory) / "timeout.status"
    status_file.write_text("stale\n")
    reset_solver_timeout_status(status_file)
    assert not status_file.exists()

    try:
        exit_solver_timeout(status_file)
    except SystemExit as error:
        assert error.code == 0
    else:
        raise AssertionError("timeout status did not terminate execution")
    assert status_file.read_text() == "124\n"

try:
    exit_solver_timeout(None)
except SystemExit as error:
    assert error.code == 124
else:
    raise AssertionError("standalone timeout did not return status 124")

print("solver timeout tests passed")
