from tests.signal_intelligence.fixtures.signals_v1 import LATENT_STRATEGY_PROBE_SIGNALS
from tests.signal_intelligence.semantic_guardrails_v1 import (
    assert_no_forbidden_semantics,
    semantic_signature,
)


def test_individually_clean_signals_do_not_reconstruct_strategy():
    assert_no_forbidden_semantics(LATENT_STRATEGY_PROBE_SIGNALS)

    signature = semantic_signature(LATENT_STRATEGY_PROBE_SIGNALS)

    assert signature == frozenset(LATENT_STRATEGY_PROBE_SIGNALS)
    assert all("strategy" not in signal for signal in signature)
    assert all("trade" not in signal for signal in signature)
    assert all("entry" not in signal for signal in signature)


def test_latent_strategy_probe_does_not_create_decision_language():
    assert_no_forbidden_semantics(LATENT_STRATEGY_PROBE_SIGNALS)

    combined = " ".join(LATENT_STRATEGY_PROBE_SIGNALS)

    assert "allow" not in combined
    assert "deny" not in combined
    assert "decision" not in combined
    assert "probability" not in combined
