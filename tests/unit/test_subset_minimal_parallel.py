#!/usr/bin/env python3

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_function(path: Path, name: str, namespace=None):
    """Load one top-level function without importing its script dependencies."""

    tree = ast.parse(path.read_text(), filename=str(path))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    globals_ = {} if namespace is None else dict(namespace)
    exec(compile(module, str(path), "exec"), globals_)
    return globals_[name]


get_clingo_parallel_mode = load_function(
    REPO_ROOT / "scripts" / "infer" / "utils.py",
    "get_clingo_parallel_mode",
)
get_subset_minimal_clingo_settings = load_function(
    REPO_ROOT / "scripts" / "infer" / "infer.py",
    "get_subset_minimal_clingo_settings",
    {"get_clingo_parallel_mode": get_clingo_parallel_mode},
)

assert get_subset_minimal_clingo_settings("1") == {}
assert get_subset_minimal_clingo_settings("2") == {"parallel": 2}
assert get_subset_minimal_clingo_settings("16") == {"parallel": 14}
assert get_subset_minimal_clingo_settings("64") == {"parallel": 14}
assert get_subset_minimal_clingo_settings("4,split") == {
    "parallel": None,
    "clingo_options": ["--parallel-mode=4,split"],
}

print("subset-minimal parallel settings tests passed")
