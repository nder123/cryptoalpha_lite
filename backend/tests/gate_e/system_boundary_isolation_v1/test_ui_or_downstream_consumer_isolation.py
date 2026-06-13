from tests.gate_e.system_boundary_isolation_v1.fixtures import (
    DOWNSTREAM_CONSUMER_TRAPS,
    RAW_SIGNAL_STREAMS,
)

DOWNSTREAM_LEAKAGE_LANGUAGE = (
    "strategy",
    "decision logic",
    "scenario",
    "policy inference",
    "trading",
    "aggregates",
)


def test_downstream_consumers_cannot_reconstruct_strategy_or_decision_logic():
    for signal_stream in RAW_SIGNAL_STREAMS:
        downstream_output = tuple(
            {"display_value": signal, "semantic_role": "raw_signal"}
            for signal in signal_stream
        )

        for entry, signal in zip(downstream_output, signal_stream, strict=True):
            assert entry["display_value"] == signal
            serialized = " ".join(entry.values()).lower()
            assert all(term not in serialized for term in DOWNSTREAM_LEAKAGE_LANGUAGE)


def test_downstream_consumer_leakage_outputs_are_forbidden():
    for output in DOWNSTREAM_CONSUMER_TRAPS:
        normalized = output.lower()
        assert any(term in normalized for term in DOWNSTREAM_LEAKAGE_LANGUAGE)
