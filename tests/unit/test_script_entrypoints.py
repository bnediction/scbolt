import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def calls_parse_args(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "parse_args"
        for child in ast.walk(node)
    )


def is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    ):
        return False
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "main"
        for child in ast.walk(node)
    )


checked = []
for path in sorted(SCRIPTS_DIR.rglob("*.py")):
    tree = ast.parse(path.read_text(), filename=str(path))
    if not calls_parse_args(tree):
        continue

    relative_path = path.relative_to(REPO_ROOT)
    checked.append(relative_path)
    main = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        ),
        None,
    )
    assert main is not None, f"missing top-level main(): {relative_path}"
    assert any(is_main_guard(node) for node in tree.body), (
        f"missing __main__ guard: {relative_path}"
    )
    assert not any(
        calls_parse_args(node)
        for node in tree.body
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ), f"parse_args() runs during import: {relative_path}"
    nested_functions = [
        node
        for node in ast.walk(main)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not main
    ]
    assert not nested_functions, f"helper defined inside main(): {relative_path}"

assert checked, "no executable Python scripts found"
print(f"script entrypoint tests passed ({len(checked)} scripts)")
