from typing import Any

from app.services.validation.core import ValidationCore


class ValidationShadowAdapter:
    """
    Runs ValidationCore in parallel (shadow mode).
    Does NOT influence execution path.
    """

    def __init__(self, core: ValidationCore):
        self.core = core

    def run_shadow_validation(
        self, decision: Any, execution: Any = None, event: Any = None
    ):
        """
        Executes all validation phases in parallel to real system.
        Returns snapshot for comparison only.
        """

        return {
            "pre": self.core.validate_before_execution(decision),
            "execution": (
                self.core.validate_execution(execution, decision) if execution else None
            ),
            "contract": self.core.validate_contracts(event) if event else None,
        }
