import sys
from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

configure_minimum_network_objectives = import_module(
    "scbolt.inference"
).configure_minimum_network_objectives


class FakeBoNesis:
    def __init__(self):
        self.programs = []

    def custom(self, program):
        self.programs.append(program)


bo = FakeBoNesis()
configure_minimum_network_objectives(bo, minimize_self_loops=False)
assert bo.programs == [
    "edge(A,B) :- clause(B,_,A,_). #minimize { 1@10,A,B: edge(A,B) }.",
]

bo = FakeBoNesis()
configure_minimum_network_objectives(bo, minimize_self_loops=True)
assert bo.programs == [
    "edge(A,B) :- clause(B,_,A,_). #minimize { 1@10,A,B: edge(A,B) }.",
    "#minimize { 1@1,A: edge(A,A) }.",
]

print("inference objective tests passed")
