#!/usr/bin/env python

import contextlib
import datetime
import os
import sys
import warnings
from pathlib import Path
from typing import Iterator, Mapping, Optional, Union


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


def print_task(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - TASK - {message}",
        file=file,
        flush=flush,
    )
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
    print(
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - INFO - {message}",
        file=file,
        flush=flush,
    )
    return None


def print_options(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - OPTIONS - {message}",
        file=file,
        flush=flush,
    )
    return None


def print_warning(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - WARNING - {message}",
        file=file,
        flush=flush,
    )
    return None


def print_debug(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - DEBUG - {message}",
        file=file,
        flush=flush,
    )
    return None


def print_result(message: Optional[str] = None, file=sys.stdout, flush=True) -> None:
    print(
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - RESULT - {message}",
        file=file,
        flush=flush,
    )
    return None
