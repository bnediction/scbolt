#!/usr/bin/env python3

import ast
import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]

REQUIRED_EXPRESSION_SCRIPTS = {
    "scripts/bin/bin_cells_scboolseq.py",
    "scripts/bin/bin_dea.py",
    "scripts/clust/clustering.py",
    "scripts/clust/dea.py",
    "scripts/clust/integration.py",
    "scripts/prep/filter.py",
    "scripts/prep/hvg.py",
    "scripts/prep/norm.py",
    "scripts/traj/potency.py",
    "scripts/traj/velocity.py",
}

NAMED_DEFAULT_EXPRESSION_SCRIPTS = {
    "scripts/bin/bin_clust_scboolseq.py": "bin",
}


def expression_argument(path: Path) -> ast.Call:
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if any(
            isinstance(argument, ast.Constant) and argument.value == "--expression"
            for argument in node.args
        ):
            return node
    raise AssertionError(f"--expression argument not found: {path}")


def keyword_value(call: ast.Call, name: str):
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value
    return None


for relative_path in REQUIRED_EXPRESSION_SCRIPTS:
    call = expression_argument(REPO / relative_path)
    assert keyword_value(call, "required") is True, relative_path
    assert keyword_value(call, "default") is None, relative_path

for relative_path, expected_default in NAMED_DEFAULT_EXPRESSION_SCRIPTS.items():
    call = expression_argument(REPO / relative_path)
    assert keyword_value(call, "default") == expected_default, relative_path

for path in (REPO / "scripts").rglob("*.py"):
    assert "Default: adata.X." not in path.read_text(), path

conversion_source = (REPO / "scripts/utils/adata_conversion.py").read_text()
assert '--expression is required when converting AnnData to CSV' in conversion_source

spec = importlib.util.spec_from_file_location(
    "scbolt_anndata",
    REPO / "lib/scbolt/omics/_anndata.py",
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class FakeAnnData:
    def __init__(self):
        self.X = object()
        self.layers = {"counts": object(), "correct": object()}


adata = FakeAnnData()
module.drop_expression_matrices(adata, layers=("correct", "missing"))
assert adata.X is None
assert set(adata.layers) == {"counts"}

selection, added, unavailable = module.include_available_features(
    ["Hvg1", "Hvg2"],
    ["Hvg2", "Rara", "Missing", "Rara", "Spi1"],
    ["Hvg1", "Hvg2", "Rara", "Spi1"],
)
assert selection == ["Hvg1", "Hvg2", "Rara", "Spi1"]
assert added == ["Rara", "Spi1"]
assert unavailable == ["Missing"]

print("expression layer tests passed")
