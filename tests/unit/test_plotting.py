import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location(
    "scbolt_plotting",
    REPO / "lib/scbolt/omics/_plotting.py",
)
plotting = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(plotting)


class FakePlotting:
    @staticmethod
    def get_color(name):
        assert name == "black"
        return "#111111"


legend = plotting.embedding_legend(FakePlotting())
assert legend["bbox_to_anchor"] == (1.05, 0.5)
assert legend["loc"] == "center left"
assert legend["ncol"] == 1
assert legend["edgecolor"] == "#111111"
assert "title" not in legend

legend = plotting.embedding_legend(
    FakePlotting(),
    title="macrostates",
    ncol=2,
    n_components=3,
)
assert legend["title"] == "macrostates"
assert legend["ncol"] == 2
assert legend["bbox_to_anchor"] == (1.2, 0.5)

print("plotting tests passed")
