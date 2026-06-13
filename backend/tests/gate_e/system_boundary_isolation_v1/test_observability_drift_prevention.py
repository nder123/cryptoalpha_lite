from tests.gate_e.system_boundary_isolation_v1.fixtures import RAW_SIGNAL_STREAMS

OBSERVABILITY_DRIFT_LANGUAGE = (
    "score",
    "scoring",
    "performance interpretation",
    "evaluation",
    "implicit evaluation",
    "rank",
    "rating",
)


def test_monitoring_metrics_do_not_create_scores_or_evaluation_layer():
    for signal_stream in RAW_SIGNAL_STREAMS:
        metric_output = tuple(
            {"signal": signal, "metric_type": "observation"} for signal in signal_stream
        )

        for metric in metric_output:
            serialized = " ".join(metric.values()).lower()
            assert all(term not in serialized for term in OBSERVABILITY_DRIFT_LANGUAGE)


def test_observability_interpretation_outputs_are_forbidden():
    forbidden_outputs = (
        "monitoring score increased",
        "metrics create performance interpretation",
        "observability formed implicit evaluation layer",
        "signals ranked by external monitor",
    )

    for output in forbidden_outputs:
        normalized = output.lower()
        assert any(term in normalized for term in OBSERVABILITY_DRIFT_LANGUAGE)
