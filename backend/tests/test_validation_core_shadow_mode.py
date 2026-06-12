from app.services.validation.core import ValidationCore
from app.services.validation.shadow_adapter import ValidationShadowAdapter


class DummyPre:
    def validate_before_execution(self, decision):
        return {"pre": True}


class DummyRuntime:
    def validate_boundary_compliance(self, execution, decision):
        return {"runtime": True}


class DummyContracts:
    def validate(self, event):
        return {"contract": True}


def test_shadow_mode_does_not_affect_runtime():
    core = ValidationCore(
        pre_execution_gate=DummyPre(),
        runtime_enforcer=DummyRuntime(),
        contracts=DummyContracts(),
    )

    shadow = ValidationShadowAdapter(core)

    result = shadow.run_shadow_validation(
        decision="dec",
        execution="exec",
        event="event",
    )

    assert result["pre"] == {"pre": True}
    assert result["execution"] == {"runtime": True}
    assert result["contract"] == {"contract": True}


def test_shadow_mode_is_optional():
    core = ValidationCore()

    shadow = ValidationShadowAdapter(core)

    result = shadow.run_shadow_validation("dec")

    assert result == {
        "pre": None,
        "execution": None,
        "contract": None,
    }
