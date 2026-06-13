from pathlib import Path


def test_signal_layer_stabilization_contract_v1_document_exists():
    assert _contract_path().is_file()


def test_signal_layer_stabilization_contract_v1_contains_required_sections():
    content = _contract_path().read_text()

    for section in (
        "## A. Core Principle",
        "## B. Signal Purity Rule",
        "## C. Evidence Constraint",
        "## D. Signal Isolation Rule",
        "## E. Temporal Rule",
        "## F. Signal Composition Rule",
        "## G. Forbidden Leakage Patterns",
    ):
        assert section in content


def _contract_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "signal_intelligence"
        / "signal_layer_stabilization_contract_v1.md"
    )
