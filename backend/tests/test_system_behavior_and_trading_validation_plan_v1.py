from pathlib import Path


def test_system_behavior_and_trading_validation_plan_v1_document_exists():
    assert _plan_path().is_file()


def test_system_behavior_and_trading_validation_plan_v1_contains_required_sections():
    content = _plan_path().read_text()

    for section in (
        "## A. Purpose",
        "## B. Validation Loop",
        "## C. Signal Quality Layer",
        "## D. Decision Utility Layer",
        "## E. Execution Reality Layer",
        "## F. Regime Robustness Layer",
        "## G. System Drift Layer",
        "## H. Evaluation Artifacts",
        "## I. Non-Goals",
        "## J. Acceptance Criteria",
    ):
        assert section in content


def test_system_behavior_and_trading_validation_plan_v1_is_measurement_only():
    content = _plan_path().read_text()

    required_phrases = (
        "It is not an architecture layer, not a Gate layer",
        "The plan measures behavior only.",
        "DATA",
        "SIGNAL",
        "DECISION",
        "EXECUTION SIMULATION",
        "METRICS",
        "must not submit live orders",
    )

    for phrase in required_phrases:
        assert phrase in content


def test_system_behavior_and_trading_validation_plan_v1_preserves_constraints():
    content = _plan_path().read_text()

    forbidden_additions = (
        "New Gates.",
        "New isolation layers.",
        "Runtime guardrails.",
        "Production trading behavior.",
        "Auto-execution.",
        "Strategy implementation.",
        "Scoring or ranking implementation.",
        "ValidationCore changes.",
        "ContractRegistry changes.",
        "Signal, decision, policy, or execution pipeline changes.",
    )

    for forbidden_addition in forbidden_additions:
        assert forbidden_addition in content


def _plan_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "behavior_validation"
        / "system_behavior_and_trading_validation_plan_v1.md"
    )
