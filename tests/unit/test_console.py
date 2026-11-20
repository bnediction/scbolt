import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from scbolt import console  # noqa: E402


terminal = io.StringIO()


@contextlib.contextmanager
def open_test_terminal():
    yield terminal


with tempfile.TemporaryDirectory() as directory:
    logfile = Path(directory) / "scbolt.log"
    environment = {
        "LOGFILE": str(logfile),
        "SCBOLT_LOGGING_TO_FILE": "true",
        "TQDM_TO_TTY": "1",
    }
    stdout = io.StringIO()
    with (
        mock.patch.dict(os.environ, environment),
        mock.patch.object(console, "open_terminal_stream", open_test_terminal),
        contextlib.redirect_stdout(stdout),
    ):
        console.print_info("ordered output")

        explicit = io.StringIO()
        console.print_warning("explicit output", file=explicit)

    assert stdout.getvalue() == ""
    assert terminal.getvalue() == logfile.read_text()
    assert terminal.getvalue().endswith(" - INFO - ordered output\n")
    assert explicit.getvalue().endswith(" - WARNING - explicit output\n")
    assert "explicit output" not in logfile.read_text()

    owner_file = Path(directory) / "terminal-owner"
    owner_file.touch()
    owned_terminal = io.StringIO()

    @contextlib.contextmanager
    def open_owned_terminal():
        yield console._TerminalStream(owned_terminal)

    owned_environment = {
        **environment,
        "SCBOLT_TERMINAL_OWNER_FILE": str(owner_file),
    }
    with (
        mock.patch.dict(os.environ, owned_environment),
        mock.patch.object(console, "open_terminal_stream", open_owned_terminal),
    ):
        console.print_debug("owned terminal output")
        owner_file.unlink()
        console.print_debug("released terminal output")

    assert "owned terminal output" in owned_terminal.getvalue()
    assert "released terminal output" not in owned_terminal.getvalue()
    assert "released terminal output" in logfile.read_text()

    @contextlib.contextmanager
    def unavailable_terminal():
        raise OSError("no controlling terminal")
        yield

    stdout = io.StringIO()
    with (
        mock.patch.dict(os.environ, environment),
        mock.patch.object(console, "open_terminal_stream", unavailable_terminal),
        contextlib.redirect_stdout(stdout),
    ):
        console.print_task("stdout fallback")

    assert stdout.getvalue().endswith(" - TASK - stdout fallback\n")
    assert "stdout fallback" not in logfile.read_text()

print("console output tests passed")
