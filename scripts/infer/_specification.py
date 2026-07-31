"""Validation helpers for Boolean model specifications."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SPECIFICATION_SECTIONS = (
    "constraints",
    "important-nodes",
    "mandatory-nodes",
    "forbidden-nodes",
)


def normalize_model_specification(value: Any) -> dict[str, list[str]]:
    """Validate and normalize a Boolean model specification mapping."""

    if not isinstance(value, Mapping):
        raise ValueError("model specification must be a YAML mapping")

    unknown_sections = sorted(set(value) - set(SPECIFICATION_SECTIONS))
    if unknown_sections:
        raise ValueError(
            "unknown model specification section(s): "
            + ", ".join(unknown_sections)
        )
    if "constraints" not in value:
        raise ValueError("missing model specification section: constraints")

    specification = {}
    for key in SPECIFICATION_SECTIONS:
        values = value.get(key)
        if values is None:
            specification[key] = []
            continue
        if not isinstance(values, list):
            raise ValueError(
                f"model specification section '{key}' must be a list"
            )
        if not all(isinstance(item, str) for item in values):
            raise ValueError(
                f"model specification section '{key}' must contain only strings"
            )
        specification[key] = values

    return specification
