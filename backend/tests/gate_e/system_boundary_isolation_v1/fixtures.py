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

CONSUMER_AGGREGATION_TRAPS = (
    "market view reconstructed from signal stream",
    "consumer interpretation layer inferred state",
    "external observer built scenario from signals",
    "downstream consumer inferred strategy",
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
