from tests.gate_e.system_boundary_isolation_v1.fixtures import (
    LOGGING_INFERENCE_TRIGGERS,
    RAW_SIGNAL_STREAMS,
)

LOGGING_INFERENCE_LANGUAGE = (
    "system health interpretation",
    "hidden state",
    "narrative",
    "scenario",
    "infers",
    "explains",
)


def test_logging_layer_keeps_signals_as_data_transport():
    for signal_stream in RAW_SIGNAL_STREAMS:
        log_output = tuple(
            {"signal": signal, "kind": "observation"} for signal in signal_stream
        )

        assert len(log_output) == len(signal_stream)
        for entry, signal in zip(log_output, signal_stream, strict=True):
            assert entry == {"signal": signal, "kind": "observation"}
            serialized = " ".join(entry.values()).lower()
            assert all(term not in serialized for term in LOGGING_INFERENCE_LANGUAGE)


def test_logging_inference_outputs_are_forbidden():
    for output in LOGGING_INFERENCE_TRIGGERS:
        normalized = output.lower()
        assert any(term in normalized for term in LOGGING_INFERENCE_LANGUAGE)
