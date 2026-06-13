from pathlib import Path


def test_signal_inventory_and_evidence_model_v1_document_exists():
    assert _design_doc_path().is_file()


def test_signal_inventory_and_evidence_model_v1_contains_required_sections():
    content = _design_doc_path().read_text()

    for section in (
        "## A. Signal Definition",
        "## B. Evidence Definition",
        "## C. Signal Lifecycle",
        "## D. Evidence Authority Rules",
        "## E. Candidate Signal Catalog",
        "## F. Risks",
    ):
        assert section in content


def _design_doc_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "signal_intelligence"
        / "signal_inventory_and_evidence_model_v1.md"
    )
