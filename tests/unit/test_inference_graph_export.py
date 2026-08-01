import sys
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

write_influence_graph = import_module("scbolt.inference").write_influence_graph


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

with TemporaryDirectory() as tmpdir:
    outdir = Path(tmpdir)
    write_influence_graph(
        boolean_network,
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
