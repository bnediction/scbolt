import sys
from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

get_subset_minimal_clingo_settings = import_module(
    "scbolt.runtime"
).get_subset_minimal_clingo_settings

assert get_subset_minimal_clingo_settings("1") == {}
assert get_subset_minimal_clingo_settings("2") == {"parallel": 2}
assert get_subset_minimal_clingo_settings("16") == {"parallel": 14}
assert get_subset_minimal_clingo_settings("64") == {"parallel": 14}
assert get_subset_minimal_clingo_settings("4,split") == {
    "parallel": None,
    "clingo_options": ["--parallel-mode=4,split"],
}

print("subset-minimal parallel settings tests passed")
