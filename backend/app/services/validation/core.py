from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.events import CTOAiDecision, TradeAction
from app.services.runtime_enforcer import RuntimeBoundaryResult
from app.services.validation.contract_registry import ContractRegistry


@dataclass(frozen=True)
class ValidationContext:
    runtime_events: Sequence[object] = ()
    runtime_decisions: Sequence[object] = ()
    runtime_executions: Sequence[object] = ()


@dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class _PreExecutionGate(Protocol):
    def validate_before_execution(self, decision: object) -> object: ...


class _RuntimeEnforcer(Protocol):
    def validate_boundary_compliance(
        self,
        events: Sequence[object],
        decisions: Sequence[object],
        executions: Sequence[object],
    ) -> object: ...


class _Contracts(Protocol):
    def validate(self, decision: object, context: object) -> object: ...


class ValidationCore:
    """
    Shadow orchestrator for validation layers.

    IMPORTANT:
    - This is a wrapper ONLY
    - No logic migration yet
    - No behavioral changes
    """

    def __init__(
        self,
        pre_execution_gate: _PreExecutionGate | None = None,
        runtime_enforcer: _RuntimeEnforcer | None = None,
        contracts: _Contracts | None = None,
    ) -> None:
        self.pre_execution_gate = pre_execution_gate
        self.runtime_enforcer = runtime_enforcer
        self.contracts = contracts
        self.contract_registry = ContractRegistry()

    def evaluate(self, decision: object, context: object) -> ValidationResult:
        """
        SINGLE SOURCE OF TRUTH (shadow mode only)

        Returns:
            ValidationResult (allowed/denied + reasons)
        """
        contract_result = self._run_contracts(decision)
        pre_result = self._run_pre_gate(decision)
        runtime_result = self._read_runtime_enforcer(context, decision)

        return self._merge(contract_result, pre_result, runtime_result)

    # -----------------------------
    # Pre-execution validation
    # -----------------------------
    def validate_before_execution(self, decision: object):
        """
        Delegates to existing pre_execution_gate (no modification)
        """
        if self.pre_execution_gate is None:
            return None
        return self.pre_execution_gate.validate_before_execution(decision)

    # -----------------------------
    # Execution validation (post fact)
    # -----------------------------
    def validate_execution(self, execution: object, decision: object):
        """
        Delegates to runtime_enforcer (no modification)
        """
        if self.runtime_enforcer is None:
            return None
        return self.runtime_enforcer.validate_boundary_compliance(execution, decision)

    # -----------------------------
    # Contract validation (optional)
    # -----------------------------
    def validate_contracts(self, event: object):
        """
        Delegates to contracts layer (no modification)
        """
        if self.contracts is None:
            return None
        return self.contracts.validate(event)

    def _run_contracts(self, decision: object) -> ValidationResult:
        result = self.contract_registry.evaluate(_contract_payload(decision))
        return _normalize_result(result, fallback_reason="CONTRACT_DENIED")

    def _run_pre_gate(self, decision: object) -> ValidationResult:
        if self.pre_execution_gate is None:
            return ValidationResult(allowed=True)
        return _normalize_result(
            self.pre_execution_gate.validate_before_execution(decision),
            fallback_reason="PRE_EXECUTION_DENIED",
        )

    def _read_runtime_enforcer(
        self, context: object, decision: object
    ) -> ValidationResult:
        if self.runtime_enforcer is None:
            return ValidationResult(allowed=True)

        validation_context = (
            context if isinstance(context, ValidationContext) else ValidationContext()
        )
        try:
            result = self.runtime_enforcer.validate_boundary_compliance(
                validation_context.runtime_events,
                validation_context.runtime_decisions,
                validation_context.runtime_executions,
            )
        except TypeError:
            result = self.runtime_enforcer.validate_boundary_compliance(decision)
        return _normalize_result(result, fallback_reason="RUNTIME_VIOLATION")

    def _merge(
        self,
        contract_result: ValidationResult,
        pre_result: ValidationResult,
        runtime_result: ValidationResult,
    ) -> ValidationResult:
        reasons: list[str] = []
        warnings: list[str] = []

        if not contract_result.allowed:
            reasons.extend(_prefixed("contract", contract_result.reasons))

        warnings.extend(_prefixed("pre", pre_result.reasons))
        warnings.extend(_prefixed("pre", pre_result.warnings))
        warnings.extend(_prefixed("runtime", runtime_result.reasons))
        warnings.extend(_prefixed("runtime", runtime_result.warnings))

        return ValidationResult(
            allowed=not reasons,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
        )


def _normalize_result(result: object, *, fallback_reason: str) -> ValidationResult:
    if result is None:
        return ValidationResult(allowed=True)
    if isinstance(result, ValidationResult):
        return result
    if isinstance(result, RuntimeBoundaryResult):
        return ValidationResult(
            allowed=result.ok,
            reasons=tuple(violation.code for violation in result.violations),
        )
    if isinstance(result, bool):
        return ValidationResult(
            allowed=result,
            reasons=() if result else (fallback_reason,),
        )
    if isinstance(result, Mapping):
        allowed_value = result.get("allowed")
        if allowed_value is None:
            allowed_value = result.get("ok")
        if allowed_value is None:
            allowed_value = result.get("valid")
        allowed = allowed_value is not False
        reasons = _string_items(result.get("reasons"))
        if not reasons:
            reasons = _string_items(result.get("violations"))
        if not allowed and not reasons:
            reasons = (fallback_reason,)
        return ValidationResult(
            allowed=allowed,
            reasons=reasons,
            warnings=_string_items(result.get("warnings")),
        )
    return ValidationResult(allowed=True)


def _contract_payload(decision: object) -> dict[str, object]:
    if isinstance(decision, CTOAiDecision):
        return {
            "trace_id": decision.meta.get("trace_id"),
            "decision": _contract_decision_value(decision.action),
        }
    if isinstance(decision, Mapping):
        return {
            "trace_id": decision.get("trace_id"),
            "decision": _mapping_decision_value(decision),
        }
    return {
        "trace_id": None,
        "decision": None,
    }


def _mapping_decision_value(decision: Mapping[object, object]) -> object:
    value = decision.get("decision")
    if value is not None:
        return value
    return _contract_decision_value(decision.get("action"))


def _contract_decision_value(value: object) -> object:
    if isinstance(value, TradeAction):
        return value.value.upper()
    if isinstance(value, str):
        return value.upper()
    return value


def _string_items(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    return (str(value),)


def _prefixed(source: str, items: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"{source}:{item}" for item in items)
