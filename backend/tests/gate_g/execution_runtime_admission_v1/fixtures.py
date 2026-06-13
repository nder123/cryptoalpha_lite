VALID_ADMISSION_OBJECTS = (
    {
        "admission_id": "gate-g-admission-001",
        "admission_token": "explicit-gate-g-admission",
        "gate_g_approved": True,
        "validated_decision_ref": "decision-allow-001",
        "signal_context": None,
        "policy_context": None,
        "execution_permitted": True,
    },
    {
        "admission_id": "gate-g-admission-002",
        "admission_token": "explicit-gate-g-admission",
        "gate_g_approved": True,
        "validated_decision_ref": "decision-allow-002",
        "signal_context": None,
        "policy_context": None,
        "execution_permitted": True,
    },
)

INVALID_EXECUTION_ATTEMPTS = (
    {
        "attempt_id": "implicit-trigger",
        "source": "runtime",
        "payload": "implicit execution trigger",
        "admission_token": None,
        "gate_g_approved": False,
        "execution_permitted": False,
    },
    {
        "attempt_id": "auto-decision",
        "source": "decision",
        "payload": "auto-execution on decision",
        "admission_token": None,
        "gate_g_approved": False,
        "execution_permitted": False,
    },
    {
        "attempt_id": "hidden-pipeline",
        "source": "pipeline",
        "payload": "hidden execution pipeline activation",
        "admission_token": None,
        "gate_g_approved": False,
        "execution_permitted": False,
    },
)

DECISION_WITHOUT_ADMISSION_CASES = (
    {
        "decision": "buy",
        "validated_decision_ref": "decision-allow-001",
        "admission_token": None,
        "gate_g_approved": False,
        "execution_engine_started": False,
    },
    {
        "decision": "sell",
        "validated_decision_ref": "decision-allow-002",
        "admission_token": None,
        "gate_g_approved": False,
        "execution_engine_started": False,
    },
)

BYPASS_SIMULATION_CASES = (
    {
        "source": "signal",
        "payload": "volatility increased",
        "bypass_attempt": "signal to execution bypass",
        "admission_token": None,
        "execution_permitted": False,
    },
    {
        "source": "policy",
        "payload": "policy suggests execution",
        "bypass_attempt": "policy to execution bypass",
        "admission_token": None,
        "execution_permitted": False,
    },
    {
        "source": "decision",
        "payload": "validated decision",
        "bypass_attempt": "decision to execution bypass",
        "admission_token": None,
        "execution_permitted": False,
    },
)

ENGINE_REJECTED_INPUTS = (
    {
        "input_type": "raw_signal",
        "payload": "liquidity reduced",
        "validated_decision_ref": None,
        "admission_token": None,
    },
    {
        "input_type": "unverified_decision",
        "payload": "decision status unknown",
        "validated_decision_ref": None,
        "admission_token": None,
    },
    {
        "input_type": "policy_suggestion",
        "payload": "policy suggests execution",
        "validated_decision_ref": None,
        "admission_token": None,
    },
)
