from tests.gate_e.system_boundary_isolation_v1.fixtures import (
    CONSUMER_AGGREGATION_TRAPS,
    RAW_SIGNAL_STREAMS,
)

FORBIDDEN_RECONSTRUCTION_LANGUAGE = (
    "market view",
    "interpretation",
    "state",
    "scenario",
    "strategy",
    "narrative",
)


def test_external_consumers_transport_atomic_signals_only():
    for signal_stream in RAW_SIGNAL_STREAMS:
        consumer_output = tuple(signal_stream)

        assert consumer_output == signal_stream
        for signal in consumer_output:
            normalized = signal.lower()
            assert all(
                term not in normalized for term in FORBIDDEN_RECONSTRUCTION_LANGUAGE
            )


def test_external_semantic_reconstruction_outputs_are_forbidden():
    for output in CONSUMER_AGGREGATION_TRAPS:
        normalized = output.lower()
        assert any(term in normalized for term in FORBIDDEN_RECONSTRUCTION_LANGUAGE)
