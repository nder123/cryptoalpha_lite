DECISION_TRAP_SIGNALS = (
    "volatility high",
    "liquidity shift observed",
    "trend continuation context observed",
    "volume expanded",
    "spread widened",
    "execution latency increased",
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

EXECUTION_BIASED_INPUTS = (
    "price variance increased",
    "volume expanded",
    "book depth decreased",
    "fill ratio decreased",
    "quote update rate slowed",
    "slippage increased",
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

FORBIDDEN_EXECUTION_INTENT_OUTPUTS = (
    "prepare execution",
    "submit order",
    "route trade",
    "increase position",
    "reduce position",
    "execute strategy",
)

FORBIDDEN_CROSS_LAYER_OUTPUTS = (
    "signals map to allowed true",
    "signals map to denied false",
    "observations trigger validation policy",
    "signal cluster overrides decision layer",
    "implicit policy inferred from signal set",
)
