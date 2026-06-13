VALID_DECISIONS = (
    {
        "decision_id": "decision-allow-001",
        "validation_allowed": True,
        "decision_state": "validated",
    },
    {
        "decision_id": "decision-allow-002",
        "validation_allowed": True,
        "decision_state": "validated",
    },
)

INVALID_EXECUTION_TRIGGERS = (
    "buy",
    "sell",
    "open position",
    "auto execution enabled",
    "implicit execution trigger",
    "hidden execution pipeline activation",
    "execute long",
    "submit order",
)

BYPASS_ATTEMPT_SCENARIOS = (
    {
        "source": "signal",
        "payload": "volatility increased",
        "attempt": "direct execution trigger",
    },
    {
        "source": "policy",
        "payload": "policy condition satisfied",
        "attempt": "policy execution shortcut",
    },
    {
        "source": "decision",
        "payload": "validated decision",
        "attempt": "decision execution shortcut",
    },
)

ADMISSION_REQUIRED_CASES = (
    {
        "case_id": "valid-decision-without-admission",
        "decision_verified": True,
        "admission_token": None,
        "gate_f_approved": False,
        "execution_permitted": False,
    },
    {
        "case_id": "valid-decision-with-explicit-admission",
        "decision_verified": True,
        "admission_token": "explicit-gate-f-admission",
        "gate_f_approved": True,
        "execution_permitted": True,
    },
    {
        "case_id": "unverified-decision-with-token",
        "decision_verified": False,
        "admission_token": "explicit-gate-f-admission",
        "gate_f_approved": True,
        "execution_permitted": False,
    },
)

EXECUTION_ENGINE_REJECTED_INPUTS = (
    {
        "input_type": "raw_signal",
        "payload": "liquidity reduced",
        "admission_token": None,
    },
    {
        "input_type": "unverified_decision",
        "payload": "validation status unknown",
        "admission_token": None,
    },
    {
        "input_type": "implicit_instruction",
        "payload": "execute if conditions align",
        "admission_token": None,
    },
)
