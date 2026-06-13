from random import Random

from tests.signal_intelligence.fixtures.signals_v1 import CLEAN_SIGNALS
from tests.signal_intelligence.semantic_guardrails_v1 import (
    assert_no_forbidden_semantics,
    semantic_signature,
)


def test_signal_semantics_are_order_invariant():
    baseline = semantic_signature(CLEAN_SIGNALS)
    shuffled = list(CLEAN_SIGNALS)
    Random(42).shuffle(shuffled)

    assert_no_forbidden_semantics(shuffled)
    assert semantic_signature(shuffled) == baseline


def test_repeated_deterministic_shuffles_do_not_create_priority():
    baseline = semantic_signature(CLEAN_SIGNALS)

    for seed in range(10):
        shuffled = list(CLEAN_SIGNALS)
        Random(seed).shuffle(shuffled)

        assert_no_forbidden_semantics(shuffled)
        assert semantic_signature(shuffled) == baseline
