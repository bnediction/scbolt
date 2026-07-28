#!/usr/bin/env python

import contextlib
import datetime
import os
import sys
import warnings
from pathlib import Path
from typing import Iterator, Mapping, Optional, Union

try:
    import termios
except ImportError:  # pragma: no cover - unavailable on non-POSIX systems
    termios = None


@contextlib.contextmanager
def suppress_output(
    suppress: bool = True,
    suppress_warnings: bool = True,
) -> Iterator[None]:
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
def guard_progress_input(file=sys.stdout) -> Iterator[None]:
    """Prevent typed input from corrupting a transient progress display."""

    terminal_fd = None
    original_attributes = None

    if termios is not None and getattr(file, "isatty", lambda: False)():
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


def format_message(level: str, message: Optional[str] = None) -> str:
    """Format one timestamped console message."""

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return f"{timestamp} - {level} - {message}"


def print_task(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(format_message("TASK", message), file=file, flush=flush)
    return None


def format_path(path: Union[str, Path]) -> str:
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


def format_hvg_parameters(method: str, number: Optional[int] = None) -> str:
    if number is None:
        return f"method={method}"
    return f"method={method}, number={number}"


def format_mapping(values: Mapping[object, object]) -> str:
    pairs = [f"{key} -> {value}" for key, value in values.items()]
    return "{" + ", ".join(sorted(pairs)) + "}"


def print_info(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(format_message("INFO", message), file=file, flush=flush)
    return None


def print_options(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(format_message("OPTIONS", message), file=file, flush=flush)
    return None


def print_warning(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(format_message("WARNING", message), file=file, flush=flush)
    return None


def print_debug(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(format_message("DEBUG", message), file=file, flush=flush)
    return None


def print_result(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(format_message("RESULT", message), file=file, flush=flush)
    return None
