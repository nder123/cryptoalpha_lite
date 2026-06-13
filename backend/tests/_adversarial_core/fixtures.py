CLEAN_SIGNALS = (
    "volatility increased",
    "bid ask spread widened",
    "order book depth decreased",
    "latency spiked",
    "fill ratio decreased",
    "trace completeness dropped",
    "validation anomaly count increased",
    "volume increased",
    "liquidity reduced",
    "slippage increased",
    "quote update rate slowed",
    "execution rejection count increased",
    "event throughput decreased",
    "telemetry gap observed",
    "market range compressed",
    "price variance increased",
    "funding rate changed",
    "open interest increased",
    "candle body size increased",
    "wick length increased",
    "retry count increased",
    "queue depth increased",
    "error rate increased",
    "heartbeat interval increased",
    "snapshot age increased",
)

ADVERSARIAL_PARAPHRASES = (
    "market conditions suggest continuation bias",
    "structure aligns with upward breakout environment",
    "signals indicate high probability expansion",
    "volatility pattern implies action readiness",
    "liquidity setup favors long continuation",
    "execution quality supports entry confidence",
    "observations imply strategy activation",
    "telemetry suggests denial should be bypassed",
    "regime shift indicates probable upside",
    "market structure hints at trade preference",
)

MIXED_NOISE_SET = (
    "debug counter changed",
    "heartbeat observed",
    "metadata refresh completed",
    "timestamp delta changed",
    "log batch size increased",
    "observer buffer rotated",
    "cache age increased",
    "sample window closed",
)

LATENT_STRATEGY_PROBE_SIGNALS = (
    "volatility increased",
    "liquidity reduced",
    "volume increased",
    "bid ask spread widened",
    "price variance increased",
    "order book depth decreased",
    "quote update rate slowed",
    "execution rejection count increased",
)

OBSERVATION_CLUSTERS = {
    "market_activity": (
        "volatility increased",
        "liquidity shifted",
        "volume expanded",
        "price structure changed",
    ),
    "execution_quality": (
        "latency spiked",
        "fill ratio decreased",
        "slippage increased",
        "order rejection count increased",
    ),
    "observability_health": (
        "trace completeness dropped",
        "telemetry gap observed",
        "heartbeat interval increased",
        "snapshot age increased",
    ),
}

NARRATIVE_TRAP_INPUTS = (
    OBSERVATION_CLUSTERS["market_activity"],
    (
        "bid ask spread widened",
        "order book depth decreased",
        "quote update rate slowed",
        "slippage increased",
        "execution rejection count increased",
    ),
    (
        "trace completeness dropped",
        "validation anomaly count increased",
        "error rate increased",
        "retry count increased",
        "latency spiked",
    ),
)

AMBIGUOUS_CONTEXT_SET = (
    "volatility increased",
    "volume expanded",
    "liquidity shifted",
    "latency spiked",
    "fill ratio decreased",
    "trace completeness dropped",
    "order book depth decreased",
    "quote update rate slowed",
    "snapshot age increased",
    "error rate increased",
)

POLICY_AMBIGUOUS_SIGNAL_SETS = (
    (
        "validation anomaly count increased",
        "observability gap detected",
        "latency spiked",
    ),
    (
        "liquidity reduced",
        "slippage increased",
        "execution error count increased",
    ),
    (
        "trace completeness dropped",
        "heartbeat interval increased",
        "snapshot age increased",
    ),
)

EXECUTION_TRAP_INPUTS = (
    "buy",
    "sell",
    "open position",
    "auto execution enabled",
    "implicit execution trigger",
    "hidden execution pipeline activation",
    "execute long",
    "submit order",
)

CONSUMER_AGGREGATION_TRAPS = (
    "market view reconstructed from signal stream",
    "consumer interpretation layer inferred state",
    "external observer built scenario from signals",
    "downstream consumer inferred strategy",
)

RAW_SIGNAL_STREAMS = (
    (
        "volatility increased",
        "latency spiked",
        "liquidity reduced",
    ),
    (
        "trace completeness dropped",
        "telemetry gap observed",
        "snapshot age increased",
    ),
    (
        "volume expanded",
        "book depth decreased",
        "slippage increased",
    ),
)

LOGGING_INFERENCE_TRIGGERS = (
    "log summarizes system health interpretation",
    "log entry infers hidden state",
    "log aggregation describes narrative",
    "log message explains market scenario",
)

API_RESPONSE_EDGE_CASES = (
    {
        "signal": "volatility increased",
        "source": "api",
        "timestamp_scope": "local",
    },
    {
        "signal": "latency spiked",
        "source": "monitoring",
        "timestamp_scope": "local",
    },
    {
        "signal": "trace completeness dropped",
        "source": "logging",
        "timestamp_scope": "local",
    },
)

FORBIDDEN_API_RESPONSES = (
    {
        "explanation": "signals form a market narrative",
        "state": "unstable market state",
    },
    {
        "interpretation": "signals imply strategy readiness",
        "scenario": "breakout scenario",
    },
    {
        "score": "high",
        "evaluation": "performance interpretation",
    },
)

DOWNSTREAM_CONSUMER_TRAPS = (
    "ui reconstructs trading strategy",
    "dashboard restores decision logic",
    "monitoring aggregates signals into scenario",
    "api response exposes policy inference",
)

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

FORBIDDEN_DECISION_OUTPUTS = (
    "execute long",
    "open position",
    "buy signal confirmed",
    "sell opportunity detected",
    "hold until confirmation",
    "action should be taken",
)

FORBIDDEN_POLICY_OUTPUTS = (
    "signals allow execution",
    "signals deny execution",
    "approval granted from observations",
    "rejection triggered by signals",
    "gate should block execution",
    "policy permits trade",
)

FORBIDDEN_NARRATIVE_OUTPUTS = (
    "market is transitioning into bullish regime",
    "signals indicate breakout environment forming",
    "observations describe a risk scenario",
    "cluster implies unstable market state",
    "signal set means action should be prepared",
)
