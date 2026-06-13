import ast
from pathlib import Path

CORE_DIR = Path(__file__).parent


def _tree(module_name: str) -> ast.Module:
    return ast.parse((CORE_DIR / module_name).read_text(encoding="utf-8"))


def _imports(tree: ast.Module) -> tuple[str, ...]:
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    return tuple(imported)


def test_fixtures_are_data_only():
    tree = _tree("fixtures.py")

    assert not any(isinstance(node, ast.Import | ast.ImportFrom) for node in tree.body)
    assert not any(isinstance(node, ast.FunctionDef) for node in ast.walk(tree))
    assert not any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))


def test_attacks_only_generate_cases_from_fixtures():
    tree = _tree("attacks.py")
    imports = _imports(tree)

    assert set(imports) == {"random", "tests._adversarial_core.fixtures"}
    assert "assert " not in (CORE_DIR / "attacks.py").read_text(encoding="utf-8")


def test_invariants_do_not_import_attacks_or_fixtures():
    imports = _imports(_tree("invariants.py"))

    assert imports == ("collections.abc",)


def test_runner_only_orchestrates_core_modules():
    imports = set(_imports(_tree("assertion_engine.py")))

    assert imports == {
        "collections.abc",
        "tests._adversarial_core",
        "tests._adversarial_core.fixtures",
        "tests._adversarial_core.invariants",
    }
