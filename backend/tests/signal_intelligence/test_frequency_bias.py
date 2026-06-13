from tests.signal_intelligence.fixtures.signals_v1 import CLEAN_SIGNALS
from tests.signal_intelligence.semantic_guardrails_v1 import (
    assert_no_forbidden_semantics,
    semantic_signature,
)


def test_frequency_does_not_create_weight_or_significance():
    signal = CLEAN_SIGNALS[0]
    one_occurrence = (signal,)
    repeated_occurrences = (signal,) * 10

    assert_no_forbidden_semantics(one_occurrence)
    assert_no_forbidden_semantics(repeated_occurrences)
    assert semantic_signature(repeated_occurrences) == semantic_signature(
        one_occurrence
    )


def test_repetition_does_not_change_signal_set_meaning():
    repeated_signals = CLEAN_SIGNALS + CLEAN_SIGNALS + CLEAN_SIGNALS

    assert_no_forbidden_semantics(repeated_signals)
    assert semantic_signature(repeated_signals) == semantic_signature(CLEAN_SIGNALS)
