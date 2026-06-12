import ast
import inspect

from app.services.validation import contracts
from app.services.validation.contract_registry import ContractRegistry


def test_contract_registry_deny_trace():
    registry = ContractRegistry()

    result = registry.evaluate({"trace_id": None, "decision": "ALLOW"})

    assert result["valid"] is False
    assert "trace_required" in result["violations"]


def test_contract_registry_terminal_deny():
    registry = ContractRegistry()

    result = registry.evaluate({"trace_id": "abc", "decision": "DENY"})

    assert result["valid"] is False
    assert "deny_is_terminal" in result["violations"]


def test_contract_registry_pass():
    registry = ContractRegistry()

    result = registry.evaluate({"trace_id": "abc", "decision": "ALLOW"})

    assert result["valid"] is True


def test_contracts_are_data_only():
    tree = ast.parse(inspect.getsource(contracts))

    forbidden_nodes = (
        ast.AsyncFunctionDef,
        ast.FunctionDef,
        ast.Lambda,
    )
    assert not any(isinstance(node, forbidden_nodes) for node in ast.walk(tree))

    forbidden_calls = {"eval", "exec"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls
