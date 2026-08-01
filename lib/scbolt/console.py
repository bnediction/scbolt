"""Console formatting and terminal controls shared by scBOLT commands."""

from __future__ import annotations

import contextlib
import datetime
import os
import sys
import warnings
from collections.abc import Generator, Mapping
from pathlib import Path
from typing import TextIO

try:
    import termios
except ImportError:  # pragma: no cover - unavailable on non-POSIX systems
    termios = None


@contextlib.contextmanager
def open_terminal_stream() -> Generator[TextIO, None, None]:
    """Open the controlling terminal for transient progress output."""

    with Path("/dev/tty").open("w") as stream:
        yield stream


@contextlib.contextmanager
def suppress_output(
    suppress: bool = True,
    suppress_warnings: bool = True,
) -> Generator[None, None, None]:
    """Temporarily suppress standard output and warnings."""

    with contextlib.ExitStack() as stack:
        if suppress_warnings:
            stack.enter_context(warnings.catch_warnings())
            warnings.simplefilter("ignore")

        if suppress:
            f = stack.enter_context(open(os.devnull, "w"))
            stack.enter_context(contextlib.redirect_stdout(f))

        yield


@contextlib.contextmanager
def guard_progress_input(file=sys.stdout) -> Generator[None, None, None]:
    """Guard input and hide the cursor during a transient progress display."""

    terminal_fd = None
    original_attributes = None
    cursor_hidden = False
    is_terminal = getattr(file, "isatty", lambda: False)()

    if is_terminal:
        try:
            file.write("\033[?25l")
            file.flush()
            cursor_hidden = True
        except (OSError, ValueError):
            pass

    if termios is not None and is_terminal:
        try:
            terminal_fd = file.fileno()
            original_attributes = termios.tcgetattr(terminal_fd)
            guarded_attributes = original_attributes.copy()
            guarded_attributes[3] &= ~(
                termios.ECHO | getattr(termios, "ECHONL", 0)
            )
            termios.tcsetattr(
                terminal_fd,
                termios.TCSANOW,
                guarded_attributes,
            )
        except OSError:
            terminal_fd = None
            original_attributes = None

    try:
        yield
    finally:
        if terminal_fd is not None and original_attributes is not None:
            try:
                termios.tcflush(terminal_fd, termios.TCIFLUSH)
                termios.tcsetattr(
                    terminal_fd,
                    termios.TCSANOW,
                    original_attributes,
                )
            except OSError:
                pass
        if cursor_hidden:
            try:
                file.write("\033[?25h")
                file.flush()
            except (OSError, ValueError):
                pass


def format_message(level: str, message: str | None = None) -> str:
    """Format one timestamped console message."""

    timestamp = (
        datetime.datetime.now(datetime.timezone.utc)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    )
    return f"{timestamp} - {level} - {message}"


def print_task(message: str | None = None, file=sys.stdout, flush=True) -> None:
    print(format_message("TASK", message), file=file, flush=flush)


def format_path(path: str | Path) -> str:
    path_str = os.fspath(path)
    relative_path = os.path.relpath(path_str)
    return relative_path if len(relative_path) < len(path_str) else path_str


def format_embedding(embedding: str) -> str:
    labels = {
        "umap": "UMAP",
        "tsne": "t-SNE",
        "spectral": "se",
        "se": "se",
        "pca": "PCA",
        "X_umap": "UMAP",
        "X_tsne": "t-SNE",
        "X_se": "se",
        "X_pca": "PCA",
        "X_largevis": "LargeVis",
        "X_diffmap": "diffusion map",
        "X_phate": "PHATE",
        "X_trimap": "TriMap",
    }
    if embedding in labels:
        return labels[embedding]
    if embedding.startswith("X_"):
        return embedding[2:]
    return embedding


def format_hvg_parameters(method: str, number: int | None = None) -> str:
    if number is None:
        return f"method={method}"
    return f"method={method}, number={number}"


def format_mapping(values: Mapping[object, object]) -> str:
    pairs = [f"{key} -> {value}" for key, value in values.items()]
    return "{" + ", ".join(sorted(pairs)) + "}"


def print_info(message: str | None = None, file=sys.stdout, flush=True) -> None:
    print(format_message("INFO", message), file=file, flush=flush)


def print_options(message: str | None = None, file=sys.stdout, flush=True) -> None:
    print(format_message("OPTIONS", message), file=file, flush=flush)


def print_warning(message: str | None = None, file=sys.stdout, flush=True) -> None:
    print(format_message("WARNING", message), file=file, flush=flush)


def print_debug(message: str | None = None, file=sys.stdout, flush=True) -> None:
    print(format_message("DEBUG", message), file=file, flush=flush)


def print_result(message: str | None = None, file=sys.stdout, flush=True) -> None:
    print(format_message("RESULT", message), file=file, flush=flush)


def print_node_reference(
    nodes_in_data,
    nodes_in_domain,
    domain_edges,
    **kwargs,
) -> None:
    """Print data and regulatory-domain sizes."""

    print_info(
        f"input graph: data nodes={len(nodes_in_data)}, "
        f"domain nodes={len(nodes_in_domain)}, domain edges={domain_edges}",
        **kwargs,
    )


def print_solver_options(
    mode,
    strategy,
    max_clauses,
    canonical,
    configuration=None,
    jobs=None,
    **kwargs,
) -> None:
    """Print the effective solver and Boolean encoding settings."""

    solver_options = []
    strategy = (
        "unused"
        if mode == "ignore" or mode.startswith("enum,")
        else strategy
    )
    if configuration is not None:
        solver_options.append(f"config={configuration}")
    solver_options.extend(
        [
            f"mode={mode}",
            f"strategy={strategy}",
        ]
    )
    if jobs is not None:
        solver_options.append(f"threads={jobs}")

    print_options(
        f"clingo solver: {', '.join(solver_options)}",
        **kwargs,
    )
    print_options(
        "encoding: "
        f"max clauses={max_clauses}, canonical={str(canonical).lower()}",
        **kwargs,
    )
