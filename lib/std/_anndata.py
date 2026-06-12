#!/usr/bin/env python

from collections.abc import Iterable
from typing import Any


def _canonicalize_sparse_matrix(matrix: Any) -> None:
    if hasattr(matrix, "sum_duplicates"):
        matrix.sum_duplicates()
    if hasattr(matrix, "sort_indices"):
        matrix.sort_indices()


def _canonicalize_sparse_values(values: Iterable[Any]) -> None:
    for value in values:
        _canonicalize_sparse_matrix(value)


def canonicalize_anndata(adata: Any) -> None:
    """Canonicalize sparse AnnData matrices before writing."""

    _canonicalize_sparse_matrix(adata.X)
    _canonicalize_sparse_values(adata.layers.values())
    _canonicalize_sparse_values(adata.obsp.values())
    _canonicalize_sparse_values(adata.varp.values())
    _canonicalize_sparse_values(adata.obsm.values())
    _canonicalize_sparse_values(adata.varm.values())
    if adata.raw is not None:
        _canonicalize_sparse_matrix(adata.raw.X)


def write_h5ad(adata: Any, filename: Any, **kwargs: Any) -> None:
    canonicalize_anndata(adata)
    adata.write_h5ad(filename=filename, **kwargs)
