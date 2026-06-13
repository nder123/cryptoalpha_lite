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
    (
        "volatility increased",
        "liquidity shifted",
        "volume expanded",
        "price structure changed",
    ),
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

FORBIDDEN_NARRATIVE_OUTPUTS = (
    "market is transitioning into bullish regime",
    "signals indicate breakout environment forming",
    "observations describe a risk scenario",
    "cluster implies unstable market state",
    "signal set means action should be prepared",
)
