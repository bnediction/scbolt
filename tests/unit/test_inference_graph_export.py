#!/usr/bin/env python3

import ast
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_write_influence_graph():
    """Load the export helper without importing inference dependencies."""

    path = REPO_ROOT / "scripts" / "infer" / "infer.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "write_influence_graph"
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {
        "MPBooleanNetwork": object,
        "to_bonesistools_boolean_network": lambda _: boolean_network,
    }
    exec(compile(module, str(path), "exec"), namespace)
    return namespace["write_influence_graph"]


class FakeDot:
    def __init__(self):
        self.writes = []

    def write(self, path, *, prog, format):
        self.writes.append((path, prog, format))


class FakeInfluenceGraph:
    def __init__(self):
        self.degree = [("active", 1), ("isolated", 0)]
        self.removed = []
        self.dot = FakeDot()

    def remove_nodes_from(self, nodes):
        self.removed.extend(nodes)

    def to_pydot(self):
        return self.dot


class FakeBooleanNetwork:
    def __init__(self):
        self.graph = FakeInfluenceGraph()

    def to_influence_graph(self):
        return self.graph


boolean_network = FakeBooleanNetwork()
write_influence_graph = load_write_influence_graph()

with TemporaryDirectory() as tmpdir:
    outdir = Path(tmpdir)
    write_influence_graph(
        object(),
        outdir,
        programs=("dot", "neato"),
        remove_isolated_nodes=True,
    )

    assert boolean_network.graph.removed == ["isolated"]
    assert boolean_network.graph.dot.writes == [
        (outdir / "ig.dot", "dot", "raw"),
        (outdir / "ig.neato", "neato", "raw"),
    ]

print("inference graph export tests passed")
