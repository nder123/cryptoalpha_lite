import ast
from pathlib import Path

CORE_DIR = Path(__file__).parent
CORE_SOURCE_FILES = tuple(
    path
    for path in CORE_DIR.glob("*.py")
    if path.name not in {"__init__.py"} and not path.name.startswith("test_")
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_core_is_stateless_and_class_free():
    for path in CORE_SOURCE_FILES:
        tree = _tree(path)

        assert not any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
        assert not any(
            isinstance(node, ast.AsyncFunctionDef) for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(tree)
        )


def test_core_module_state_is_constant_only():
    for path in CORE_SOURCE_FILES:
        tree = _tree(path)

        for node in tree.body:
            if isinstance(node, ast.Assign):
                assigned_names = tuple(
                    target.id for target in node.targets if isinstance(target, ast.Name)
                )
                assert assigned_names
                assert all(
                    name.isupper() or name == "Invariant" for name in assigned_names
                )


def test_core_contains_no_io_or_side_effect_calls():
    side_effect_calls = {
        "__import__",
        "eval",
        "exec",
        "open",
        "print",
    }

    for path in CORE_SOURCE_FILES:
        tree = _tree(path)
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert side_effect_calls.isdisjoint(called_names)
