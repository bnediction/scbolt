#!/usr/bin/env python

import os
import tempfile
from typing import Any, Iterable


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


def _is_tmp_path(filename: Any) -> bool:
    try:
        path = os.path.abspath(os.fspath(filename))
    except TypeError:
        return False
    tmpdir = os.path.abspath(tempfile.gettempdir())
    return os.path.commonpath([path, tmpdir]) == tmpdir


def write_h5ad(adata: Any, filename: Any, **kwargs: Any) -> None:
    canonicalize_anndata(adata)
    if "compression" not in kwargs and not _is_tmp_path(filename):
        kwargs["compression"] = "gzip"
    adata.write_h5ad(filename=filename, **kwargs)
