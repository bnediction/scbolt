import sys
from importlib import import_module
from pathlib import Path

from mpbn import MPBooleanNetwork

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "infer"))

inference = import_module("infer")

network = MPBooleanNetwork(
    {
        "HLA-DOA": "NKX3-1",
        "NKX3-1": "HLA-DOA",
    }
)
adapted = inference.to_bonesistools_boolean_network(network)
graph = adapted.to_influence_graph()

assert adapted.components == {"HLA-DOA", "NKX3-1"}
assert set(graph.edges(data="sign")) == {
    ("HLA-DOA", "NKX3-1", 1),
    ("NKX3-1", "HLA-DOA", 1),
}

print("hyphenated Boolean network export tests passed")
