#!/usr/bin/env python

from contextlib import contextmanager
import warnings


@contextmanager
def filter_scanpy_hvg_warnings():
    """Ignore pandas FutureWarnings emitted inside Scanpy HVG computation."""

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"The default of observed=False is deprecated.*",
            category=FutureWarning,
            module=r"scanpy\.preprocessing\._highly_variable_genes",
        )
        warnings.filterwarnings(
            "ignore",
            message=(
                r"The behavior of DataFrame concatenation with empty or all-NA "
                r"entries is deprecated.*"
            ),
            category=FutureWarning,
            module=r"scanpy\.preprocessing\._highly_variable_genes",
        )
        warnings.filterwarnings(
            "ignore",
            message=(
                r"The provided callable .* is currently using "
                r"SeriesGroupBy\.(mean|sum).*"
            ),
            category=FutureWarning,
            module=r"scanpy\.preprocessing\._highly_variable_genes",
        )
        yield


@contextmanager
def filter_scanpy_rank_genes_warnings():
    """Ignore pandas FutureWarnings emitted inside Scanpy rank-genes helpers."""

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"The behavior of DataFrame\.sum with axis=None is deprecated.*",
            category=FutureWarning,
            module=r"numpy\.core\.fromnumeric",
        )
        warnings.filterwarnings(
            "ignore",
            message=r"The previous implementation of stack is deprecated.*",
            category=FutureWarning,
            module=r"scanpy\.get\.get",
        )
        yield
