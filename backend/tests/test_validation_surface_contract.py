import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"

CONTRACT_RULES_ALLOWED = {
    BACKEND_APP / "services" / "validation" / "contracts.py",
    BACKEND_APP / "services" / "validation" / "contract_registry.py",
}

CONTRACT_INTERPRETER_ALLOWED = {
    BACKEND_APP / "services" / "validation" / "contract_registry.py",
}


def test_contract_rules_are_only_imported_by_registry():
    offenders: list[Path] = []

    for path in _python_sources():
        if path in CONTRACT_RULES_ALLOWED:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported = {alias.name for alias in node.names}
                if "CONTRACT_RULES" in imported:
                    offenders.append(path)
            elif isinstance(node, ast.Name) and node.id == "CONTRACT_RULES":
                offenders.append(path)

    assert offenders == []


def test_contract_rule_interpretation_is_not_duplicated_outside_registry():
    offenders: list[Path] = []

    for path in _python_sources():
        if path in CONTRACT_INTERPRETER_ALLOWED:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        if any(_looks_like_contract_rule_interpreter(node) for node in ast.walk(tree)):
            offenders.append(path)

    assert offenders == []


def _python_sources() -> list[Path]:
    return [path for path in BACKEND_APP.rglob("*.py") if path.is_file()]


def _looks_like_contract_rule_interpreter(node: ast.AST) -> bool:
    if isinstance(node, ast.Subscript):
        return _is_rule_name(node.value) and _constant_key(node.slice) in {
            "field",
            "op",
            "name",
        }
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return (
            _is_rule_name(node.func.value)
            and node.func.attr == "get"
            and bool(node.args)
            and _constant_key(node.args[0]) in {"value", "field", "op", "name"}
        )
    return False


def _is_rule_name(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "rule"


def _constant_key(node: ast.AST) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    return None
