from tests.signal_intelligence.fixtures.signals_v1 import CLEAN_SIGNALS, MIXED_NOISE_SET
from tests.signal_intelligence.semantic_guardrails_v1 import (
    assert_no_forbidden_semantics,
    semantic_signature,
)


def test_noise_does_not_mutate_existing_signal_interpretation():
    base_signals = CLEAN_SIGNALS[:8]
    noisy_signals = base_signals + MIXED_NOISE_SET

    assert_no_forbidden_semantics(base_signals)
    assert_no_forbidden_semantics(noisy_signals)
    assert semantic_signature(base_signals).issubset(semantic_signature(noisy_signals))


def test_noise_order_does_not_create_hidden_priority():
    base_signals = CLEAN_SIGNALS[:8]
    noise_first = MIXED_NOISE_SET + base_signals
    noise_last = base_signals + MIXED_NOISE_SET

    assert_no_forbidden_semantics(noise_first)
    assert_no_forbidden_semantics(noise_last)
    assert semantic_signature(noise_first) == semantic_signature(noise_last)
