import ast
from pathlib import Path

from app.services.validation.core import ValidationCore, ValidationResult
from app.services.validation.event_lineage import LineageEvent, validate_event_lineage


class PreExecutionSignal:
    def __init__(self, result: ValidationResult):
        self.result = result

    def validate_before_execution(self, decision):
        return self.result


class RuntimeSignal:
    def __init__(self, result: ValidationResult):
        self.result = result

    def validate_boundary_compliance(self, decision):
        return self.result


def _decision(trace_id: str = "trace-architecture-v2", decision: str = "ALLOW"):
    return {"trace_id": trace_id, "decision": decision}


def test_contract_is_terminal_gate_and_cannot_mask_into_warnings():
    core = ValidationCore(
        pre_execution_gate=PreExecutionSignal(
            ValidationResult(allowed=False, reasons=("PRE_GATE_DENIED",))
        ),
        runtime_enforcer=RuntimeSignal(
            ValidationResult(allowed=False, reasons=("RUNTIME_VIOLATION",))
        ),
    )

    result = core.evaluate(_decision(decision="DENY"), context={})

    assert result.allowed is False
    assert result.reasons == ("contract:deny_is_terminal",)
    assert result.warnings == ()
    assert all(not warning.startswith("contract:") for warning in result.warnings)


def test_contract_cannot_be_overridden_by_soft_layers():
    core = ValidationCore(
        pre_execution_gate=PreExecutionSignal(
            ValidationResult(allowed=True, warnings=("PRE_OBSERVED",))
        ),
        runtime_enforcer=RuntimeSignal(
            ValidationResult(allowed=True, warnings=("RUNTIME_OBSERVED",))
        ),
    )

    result = core.evaluate(_decision(decision="REJECT"), context={})

    assert result.allowed is False
    assert result.reasons == ("contract:reject_is_terminal",)
    assert result.warnings == ()


def test_pre_runtime_are_soft_only_when_contract_passes():
    core = ValidationCore(
        pre_execution_gate=PreExecutionSignal(
            ValidationResult(allowed=False, reasons=("PRE_GATE_DENIED",))
        ),
        runtime_enforcer=RuntimeSignal(
            ValidationResult(allowed=False, reasons=("RUNTIME_VIOLATION",))
        ),
    )

    result = core.evaluate(_decision(), context={})

    assert result.allowed is True
    assert result.reasons == ()
    assert result.warnings == (
        "pre:PRE_GATE_DENIED",
        "runtime:RUNTIME_VIOLATION",
    )


def test_lineage_has_no_decision_authority():
    lineage_report = validate_event_lineage(
        [
            LineageEvent(
                event_id="event-lineage-child",
                trace_id="trace-architecture-v2",
                parent_id="missing-parent",
            )
        ]
    )
    core = ValidationCore(
        pre_execution_gate=PreExecutionSignal(ValidationResult(allowed=True)),
        runtime_enforcer=RuntimeSignal(ValidationResult(allowed=True)),
    )

    result = core.evaluate(_decision(), context={})

    assert lineage_report.passed is False
    assert result.allowed is True
    assert result.reasons == ()
    assert result.warnings == ()


def test_validation_core_is_single_final_decision_owner():
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

    assert "_merge" in methods
    assert _method_returns_self_merge(methods["evaluate"])
    assert not _method_instantiates_validation_result(methods["evaluate"])


def _method_returns_self_merge(method: ast.FunctionDef) -> bool:
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


def _method_instantiates_validation_result(method: ast.FunctionDef) -> bool:
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "ValidationResult":
            return True
    return False
