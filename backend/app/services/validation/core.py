from typing import Any


class ValidationCore:
    """
    Shadow orchestrator for validation layers.

    IMPORTANT:
    - This is a wrapper ONLY
    - No logic migration yet
    - No behavioral changes
    """

    def __init__(self, pre_execution_gate=None, runtime_enforcer=None, contracts=None):
        self.pre_execution_gate = pre_execution_gate
        self.runtime_enforcer = runtime_enforcer
        self.contracts = contracts

    # -----------------------------
    # Pre-execution validation
    # -----------------------------
    def validate_before_execution(self, decision: Any):
        """
        Delegates to existing pre_execution_gate (no modification)
        """
        if self.pre_execution_gate is None:
            return None
        return self.pre_execution_gate.validate_before_execution(decision)

    # -----------------------------
    # Execution validation (post fact)
    # -----------------------------
    def validate_execution(self, execution: Any, decision: Any):
        """
        Delegates to runtime_enforcer (no modification)
        """
        if self.runtime_enforcer is None:
            return None
        return self.runtime_enforcer.validate_boundary_compliance(execution, decision)

    # -----------------------------
    # Contract validation (optional)
    # -----------------------------
    def validate_contracts(self, event: Any):
        """
        Delegates to contracts layer (no modification)
        """
        if self.contracts is None:
            return None
        return self.contracts.validate(event)
