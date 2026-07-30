#!/usr/bin/env python

from __future__ import annotations

import os
import tempfile
from typing import Any, Iterable


def include_available_features(
    selected: Iterable[str],
    requested: Iterable[str],
    available: Iterable[str],
) -> tuple[list[str], list[str], list[str]]:
    """Append available requested features while preserving selection order."""

    result = list(selected)
    selected_set = set(result)
    available_set = set(available)
    added = []
    unavailable = []
    considered = set()

    for feature in requested:
        if feature in considered:
            continue
        considered.add(feature)
        if feature not in available_set:
            unavailable.append(feature)
        elif feature not in selected_set:
            result.append(feature)
            selected_set.add(feature)
            added.append(feature)

    return result, added, unavailable


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


def drop_expression_matrices(
    adata: Any,
    layers: Iterable[str] = (),
) -> None:
    """Drop ``X`` and selected expression layers from an AnnData object."""

    adata.X = None
    for layer in layers:
        if layer in adata.layers:
            del adata.layers[layer]


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
