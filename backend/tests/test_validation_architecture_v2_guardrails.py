import ast
from itertools import product
from pathlib import Path

import pytest

from app.services.validation.core import ValidationCore, ValidationResult
from app.services.validation.event_lineage import LineageEvent, validate_event_lineage


class PreSignal:
    def __init__(self, result: ValidationResult):
        self.result = result

    def validate_before_execution(self, decision):
        return self.result


class RuntimeSignal:
    def __init__(self, result: ValidationResult):
        self.result = result

    def validate_boundary_compliance(self, decision):
        return self.result


def _decision(decision: str = "ALLOW"):
    return {"trace_id": "trace-v2-guardrails", "decision": decision}


def test_no_second_final_decision_owner():
    core_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "validation"
        / "core.py"
    )
    tree = ast.parse(core_path.read_text(), filename=str(core_path))
    validation_core = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ValidationCore"
    )
    methods = {
        node.name: node
        for node in validation_core.body
        if isinstance(node, ast.FunctionDef)
    }

    assert _returns_self_merge(methods["evaluate"])
    assert not _instantiates_validation_result(methods["evaluate"])
    assert not _assigns_allowed(methods["evaluate"])


@pytest.mark.parametrize(
    ("pre_result", "runtime_result"),
    product(
        (
            ValidationResult(allowed=True),
            ValidationResult(allowed=True, warnings=("PRE_WARNING",)),
            ValidationResult(allowed=False, reasons=("PRE_DENIED",)),
        ),
        (
            ValidationResult(allowed=True),
            ValidationResult(allowed=True, warnings=("RUNTIME_WARNING",)),
            ValidationResult(allowed=False, reasons=("RUNTIME_DENIED",)),
        ),
    ),
)
def test_contract_is_absolute(
    pre_result: ValidationResult, runtime_result: ValidationResult
):
    core = ValidationCore(
        pre_execution_gate=PreSignal(pre_result),
        runtime_enforcer=RuntimeSignal(runtime_result),
    )

    result = core.evaluate(_decision(decision="DENY"), context={})

    assert result.allowed is False
    assert result.reasons == ("contract:deny_is_terminal",)
    assert result.warnings == ()


def test_warnings_have_no_allowed_escape_path():
    core = ValidationCore()

    result = core._merge(
        ValidationResult(allowed=True),
        ValidationResult(
            allowed=True,
            warnings=("PRE_WARNING", "contract:attempted_warning_escape"),
        ),
        ValidationResult(
            allowed=True,
            warnings=("RUNTIME_WARNING", "contract:attempted_warning_escape"),
        ),
    )

    assert result.allowed is True
    assert result.reasons == ()
    assert result.warnings == (
        "pre:PRE_WARNING",
        "pre:contract:attempted_warning_escape",
        "runtime:RUNTIME_WARNING",
        "runtime:contract:attempted_warning_escape",
    )


def test_lineage_changes_do_not_influence_allowed():
    passing_lineage = validate_event_lineage(
        [
            LineageEvent(
                event_id="parent",
                trace_id="trace-v2-guardrails",
                parent_id=None,
            ),
            LineageEvent(
                event_id="child",
                trace_id="trace-v2-guardrails",
                parent_id="parent",
            ),
        ]
    )
    failing_lineage = validate_event_lineage(
        [
            LineageEvent(
                event_id="orphan",
                trace_id="trace-v2-guardrails",
                parent_id="missing-parent",
            )
        ]
    )
    core = ValidationCore(
        pre_execution_gate=PreSignal(ValidationResult(allowed=True)),
        runtime_enforcer=RuntimeSignal(ValidationResult(allowed=True)),
    )

    passing_result = core.evaluate(_decision(), context={})
    failing_result = core.evaluate(_decision(), context={})

    assert passing_lineage.passed is True
    assert failing_lineage.passed is False
    assert passing_result == failing_result == ValidationResult(allowed=True)


def test_contract_violations_cannot_land_only_in_warnings():
    core = ValidationCore()

    result = core._merge(
        ValidationResult(
            allowed=False,
            reasons=("contract_violation",),
            warnings=("contract_warning",),
        ),
        ValidationResult(allowed=True, warnings=("PRE_WARNING",)),
        ValidationResult(allowed=True, warnings=("RUNTIME_WARNING",)),
    )

    assert result.allowed is False
    assert result.reasons == ("contract:contract_violation",)
    assert result.warnings == ()


def _returns_self_merge(method: ast.FunctionDef) -> bool:
    for node in ast.walk(method):
        if not isinstance(node, ast.Return):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        func = value.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "_merge":
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "self":
            return True
    return False


def _instantiates_validation_result(method: ast.FunctionDef) -> bool:
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "ValidationResult":
            return True
    return False


def _assigns_allowed(method: ast.FunctionDef) -> bool:
    for node in ast.walk(method):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "allowed":
                return True
            if isinstance(target, ast.Attribute) and target.attr == "allowed":
                return True
    return False
