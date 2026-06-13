#!/usr/bin/env python

import contextlib
import os
import sys
import warnings

import datetime
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Optional


@contextlib.contextmanager
def single_thread() -> Iterator[None]:
    try:
        from threadpoolctl import threadpool_limits
    except ImportError:
        yield
    else:
        with threadpool_limits(limits=1):
            yield

@contextlib.contextmanager
def disable_print(disable: bool = True, disable_warnings: bool = True):
    with contextlib.ExitStack() as stack:
        if disable_warnings is True:
            stack.enter_context(warnings.catch_warnings())
            warnings.simplefilter("ignore")

        if disable is True:
            f = stack.enter_context(open(os.devnull, "w"))
            stack.enter_context(contextlib.redirect_stdout(f))

        yield

class Section(object):

    def __init__(
        self,
        init: int = 1,
        verbose: bool = True
    ):
        self.init = init
        self._i = init
        self._verbose = verbose
    
    def __call__(
        self,
        v: str,
        reset: bool = False
    ):
        self._i = self.init if reset else self._i
        if self._verbose is True:
            print(f"{self._i}) {v}")
        self._i+=1
        return None
    
    def reset(self):
        self._i = self.init
        return None
    
    def quiet(self):
        self._verbose = False
    
    def verbose(self):
        self._verbose = True

def print_task(message: Optional[str]=None, file=sys.stdout, flush=True) -> None:
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - TASK - {message}", file=file, flush=flush)
    return None

def format_path(path: str | Path) -> str:
    path_str = os.fspath(path)
    relative_path = os.path.relpath(path_str)
    return relative_path if len(relative_path) < len(path_str) else path_str


def format_embedding(embedding: str) -> str:
    labels = {
        "umap": "UMAP",
        "tsne": "t-SNE",
        "se": "spectral embedding",
        "pca": "PCA",
        "X_umap": "UMAP",
        "X_tsne": "t-SNE",
        "X_se": "spectral embedding",
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


def format_hvg_parameters(flavor: str, number: Optional[int] = None) -> str:
    if number is None:
        return f"flavor={flavor}"
    return f"flavor={flavor}, number={number}"


def format_set(values: Iterable[object]) -> str:
    return "{" + ", ".join(sorted(map(str, values))) + "}"


def format_mapping(values: Mapping[object, object]) -> str:
    pairs = [f"{key} -> {value}" for key, value in values.items()]
    return "{" + ", ".join(sorted(pairs)) + "}"


def print_info(message: Optional[str]=None, file=sys.stdout, flush=True) -> None:
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - INFO - {message}", file=file, flush=flush)
    return None

def print_warning(message: Optional[str]=None, file=sys.stdout, flush=True) -> None:
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - WARNING - {message}", file=file, flush=flush)
    return None

def print_debug(message: Optional[str]=None, file=sys.stdout, flush=True) -> None:
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - DEBUG - {message}", file=file, flush=flush)
    return None

def print_result(message: Optional[str]=None, file=sys.stdout, flush=True) -> None:
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - RESULT - {message}", file=file, flush=flush)
    return None
