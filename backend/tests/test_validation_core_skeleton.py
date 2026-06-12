from app.services.validation.core import ValidationCore


class DummyPreGate:
    def validate_before_execution(self, decision):
        return {"pre": True}


class DummyRuntime:
    def validate_boundary_compliance(self, execution, decision):
        return {"runtime": True}


class DummyContracts:
    def validate(self, event):
        return {"contract": True}


def test_validation_core_delegation():
    core = ValidationCore(
        pre_execution_gate=DummyPreGate(),
        runtime_enforcer=DummyRuntime(),
        contracts=DummyContracts(),
    )

    assert core.validate_before_execution("x") == {"pre": True}
    assert core.validate_execution("exec", "dec") == {"runtime": True}
    assert core.validate_contracts("event") == {"contract": True}


def test_validation_core_no_break_without_dependencies():
    core = ValidationCore()

    assert core.validate_before_execution("x") is None
    assert core.validate_execution("exec", "dec") is None
    assert core.validate_contracts("event") is None
