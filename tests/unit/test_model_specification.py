import sys
from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

normalize_model_specification = import_module(
    "scbolt.inference"
).normalize_model_specification


def assert_invalid(
    value,
    expected_message: str,
    error_type: type[Exception] = ValueError,
) -> None:
    try:
        normalize_model_specification(value)
    except error_type as error:
        assert str(error) == expected_message
    else:
        raise AssertionError(f"invalid specification accepted: {value!r}")


normalized = normalize_model_specification(
    {
        "constraints": ["a = fixed(obs('A'))"],
        "important-nodes": ["A"],
        "mandatory-nodes": None,
    }
)
assert normalized == {
    "constraints": ["a = fixed(obs('A'))"],
    "important-nodes": ["A"],
    "mandatory-nodes": [],
    "forbidden-nodes": [],
}

assert_invalid([], "model specification must be a YAML mapping", TypeError)
assert_invalid({}, "missing model specification section: constraints")
assert_invalid(
    {"constraints": [], "unknown": []},
    "unknown model specification section(s): unknown",
)
assert_invalid(
    {"constraints": "a = b"},
    "model specification section 'constraints' must be a list",
    TypeError,
)
assert_invalid(
    {"constraints": [1]},
    "model specification section 'constraints' must contain only strings",
    TypeError,
)

print("model specification tests passed")
