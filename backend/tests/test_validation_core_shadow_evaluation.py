from app.services.validation.core import ValidationCore, ValidationResult


class ContractLayer:
    def __init__(self, result: ValidationResult):
        self.result = result

    def validate(self, decision, context):
        return self.result


class PreExecutionHints:
    def __init__(self, result: ValidationResult):
        self.result = result

    def validate_before_execution(self, decision):
        return self.result


class RuntimeEvidence:
    def __init__(self, result: ValidationResult):
        self.result = result

    def validate_boundary_compliance(self, decision):
        return self.result


def _decision(trace_id: str | None = "trace-validation-core"):
    if trace_id is None:
        return {}
    return {"trace_id": trace_id}


def test_validation_core_shadow_evaluation_allows_valid_flow():
    core = ValidationCore(
        pre_execution_gate=PreExecutionHints(ValidationResult(allowed=True)),
        runtime_enforcer=RuntimeEvidence(ValidationResult(allowed=True)),
        contracts=ContractLayer(ValidationResult(allowed=True)),
    )

    result = core.evaluate(_decision(), context={})

    assert result == ValidationResult(allowed=True)


def test_validation_core_shadow_evaluation_denies_contract_violation():
    core = ValidationCore(
        pre_execution_gate=PreExecutionHints(ValidationResult(allowed=True)),
        runtime_enforcer=RuntimeEvidence(ValidationResult(allowed=True)),
        contracts=ContractLayer(
            ValidationResult(allowed=False, reasons=("CONTRACT_VIOLATION",))
        ),
    )

    result = core.evaluate(_decision(), context={})

    assert not result.allowed
    assert result.reasons == ("contract:CONTRACT_VIOLATION",)


def test_validation_core_shadow_evaluation_warns_on_runtime_violation_only():
    core = ValidationCore(
        pre_execution_gate=PreExecutionHints(ValidationResult(allowed=True)),
        runtime_enforcer=RuntimeEvidence(
            ValidationResult(allowed=False, reasons=("RUNTIME_VIOLATION",))
        ),
        contracts=ContractLayer(ValidationResult(allowed=True)),
    )

    result = core.evaluate(_decision(), context={})

    assert result.allowed
    assert result.reasons == ()
    assert result.warnings == ("runtime:RUNTIME_VIOLATION",)


def test_validation_core_shadow_evaluation_always_denies_missing_trace_id():
    core = ValidationCore(
        pre_execution_gate=PreExecutionHints(ValidationResult(allowed=True)),
        runtime_enforcer=RuntimeEvidence(ValidationResult(allowed=True)),
        contracts=ContractLayer(ValidationResult(allowed=True)),
    )

    result = core.evaluate(_decision(trace_id=None), context={})

    assert not result.allowed
    assert result.reasons == ("TRACE_ID_MISSING",)


def test_validation_core_overrides_non_authoritative_layers():
    core = ValidationCore(
        pre_execution_gate=PreExecutionHints(
            ValidationResult(allowed=False, reasons=("PRE_GATE_DENIED",))
        ),
        runtime_enforcer=RuntimeEvidence(
            ValidationResult(allowed=False, reasons=("RUNTIME_VIOLATION",))
        ),
        contracts=ContractLayer(ValidationResult(allowed=True)),
    )

    result = core.evaluate(_decision(), context={})

    assert result.allowed
    assert result.reasons == ()
    assert result.warnings == (
        "pre:PRE_GATE_DENIED",
        "runtime:RUNTIME_VIOLATION",
    )
