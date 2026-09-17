import sys
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

inference = import_module("scbolt.inference")
ensemble_feedback_induced_graph = inference.ensemble_feedback_induced_graph
write_influence_graph = inference.write_influence_graph


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


class FakeFeedbackGraph:
    def __init__(self, nodes):
        self.nodes = set(nodes)

    def feedback_nodes(self, *, include_selfloops):
        assert include_selfloops is False
        return set(self.nodes)


class FakeAggregatedGraph:
    def __init__(self, nodes, edges):
        self.nodes = set(nodes)
        self.edges = set(edges)

    def __iter__(self):
        return iter(self.nodes)

    def copy(self):
        return type(self)(self.nodes, self.edges)

    def remove_nodes_from(self, nodes):
        nodes = set(nodes)
        self.nodes -= nodes
        self.edges = {
            (source, target)
            for source, target in self.edges
            if source not in nodes and target not in nodes
        }


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


aggregated = FakeAggregatedGraph(
    {"A", "B", "C", "X", "Y"},
    {
        ("A", "B"),
        ("A", "C"),
        ("B", "A"),
        ("B", "C"),
        ("C", "A"),
        ("C", "B"),
        ("X", "Y"),
        ("Y", "X"),
    },
)
feedback = ensemble_feedback_induced_graph(
    [FakeFeedbackGraph({"A", "C"}), FakeFeedbackGraph({"B", "C"})],
    aggregated,
    include_selfloops=False,
)

assert feedback.nodes == {"A", "B", "C"}
assert feedback.edges == {
    ("A", "B"),
    ("A", "C"),
    ("B", "A"),
    ("B", "C"),
    ("C", "A"),
    ("C", "B"),
}
assert aggregated.nodes == {"A", "B", "C", "X", "Y"}

single_feedback = ensemble_feedback_induced_graph(
    [FakeFeedbackGraph({"A", "B"})],
    aggregated,
    include_selfloops=False,
)
assert single_feedback.nodes == {"A", "B"}

try:
    ensemble_feedback_induced_graph([], aggregated)
except ValueError as error:
    assert str(error) == "expected at least one influence graph"
else:
    raise AssertionError("empty influence graph ensembles must be rejected")

print("inference graph export tests passed")
