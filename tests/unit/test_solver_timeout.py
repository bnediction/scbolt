import argparse
import sys
import tempfile
import time
from importlib import import_module
from pathlib import Path
from threading import Event, Timer
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

runtime = import_module("scbolt.runtime")
SolverCapacityError = runtime.SolverCapacityError
SolverDeadline = runtime.SolverDeadline
SolverPatience = runtime.SolverPatience
SolverPatienceExpired = runtime.SolverPatienceExpired
SolverTimeout = runtime.SolverTimeout
close_solver_progress = runtime.close_solver_progress
exit_solver_capacity = runtime.exit_solver_capacity
exit_solver_timeout = runtime.exit_solver_timeout
format_duration = runtime.format_duration
interrupt_solver_view = runtime.interrupt_solver_view
iter_solutions = runtime.iter_solutions
next_solution = runtime.next_solution
parse_solver_timeout = runtime.parse_solver_timeout
reset_solver_timeout_status = runtime.reset_solver_timeout_status


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


class ReinitializingView:
    def __init__(self):
        self.iter_calls = 0

    def __iter__(self):
        self.iter_calls += 1
        self.solutions = iter(("solution",))
        return self

    def __next__(self):
        return next(self.solutions)


class SolveHandler:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class AsyncView:
    def __init__(self):
        self.interrupted = False
        self._solve_handler = SolveHandler()

    def interrupt(self):
        self.interrupted = True


class CapacityView:
    def __iter__(self):
        raise RuntimeError(
            "Clasp::Asp::PrgNode::PrgNode@403: Value too large for "
            "defined data type: Id out of range"
        )


class InvalidView:
    def __iter__(self):
        raise RuntimeError("unrelated solver failure")


class ProgressBar:
    def __init__(self):
        self.leave = True
        self.cleared = False
        self.closed = False

    def clear(self):
        self.cleared = True

    def close(self):
        self.closed = True


class ProgressView(ImmediateView):
    def __init__(self):
        self._progressbar = ProgressBar()


assert parse_solver_timeout("30") == 30.0
assert parse_solver_timeout("30s") == 30.0
assert parse_solver_timeout("1.5m") == 90.0
assert parse_solver_timeout("24h") == 86400.0
assert parse_solver_timeout("2d") == 172800.0
assert parse_solver_timeout("0") == 0.0
assert format_duration(30) == "30s"
assert format_duration(90) == "1m30s"
assert format_duration(1800) == "30m"
assert format_duration(9000) == "2h30m"
assert format_duration(172800) == "2d"

disabled_patience = SolverPatience(0.0)
assert disabled_patience.remaining() is None

with patch("scbolt.runtime._timeout.time.monotonic", return_value=100.0) as clock:
    patience = SolverPatience(300.0)
    clock.return_value = 200.0
    patience.ensure_remaining(120.0)
    assert patience.remaining() == 200.0

    clock.return_value = 350.0
    patience.ensure_remaining(120.0)
    assert patience.remaining() == 120.0

    patience.ensure_remaining(600.0)
    assert patience.remaining() == 300.0

    delayed_patience = SolverPatience(300.0, start_immediately=False)
    assert delayed_patience.remaining() is None
    clock.return_value = 400.0
    delayed_patience.start()
    assert delayed_patience.remaining() == 300.0
    clock.return_value = 450.0
    delayed_patience.start()
    assert delayed_patience.remaining() == 250.0

try:
    SolverPatience(1.0).ensure_remaining(-1.0)
except ValueError:
    pass
else:
    raise AssertionError("negative minimum patience was accepted")

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

view = ProgressView()
assert next_solution(view) == "solution"
assert not view._progressbar.leave
assert view._progressbar.cleared
assert view._progressbar.closed

view = ProgressView()
close_solver_progress(view)
assert not view._progressbar.leave
assert view._progressbar.cleared
assert view._progressbar.closed

view = ReinitializingView()
solutions = iter_solutions(view)
try:
    assert next(solutions) == "solution"
finally:
    solutions.close()
assert view.iter_calls == 1

view = AsyncView()
interrupt_solver_view(view)
assert view.interrupted
assert view._solve_handler.cancelled

view = AsyncView()
interrupt_solver_view(view, cancel_handler=False)
assert view.interrupted
assert not view._solve_handler.cancelled

try:
    next(iter_solutions(CapacityView()))
except SolverCapacityError as error:
    assert "268,435,455" in str(error)
else:
    raise AssertionError("Clasp program-node overflow was not normalized")

try:
    next(iter_solutions(InvalidView()))
except RuntimeError as error:
    assert type(error) is RuntimeError
    assert str(error) == "unrelated solver failure"
else:
    raise AssertionError("unrelated solver failure was suppressed")

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
        exit_solver_capacity(status_file)
    except SystemExit as error:
        assert error.code == 0
    else:
        raise AssertionError("capacity status did not terminate execution")
    assert status_file.read_text() == "125\n"

try:
    exit_solver_timeout(None)
except SystemExit as error:
    assert error.code == 124
else:
    raise AssertionError("standalone timeout did not return status 124")

try:
    exit_solver_capacity(None)
except SystemExit as error:
    assert error.code == 125
else:
    raise AssertionError("standalone capacity stop did not return status 125")

print("solver timeout tests passed")
