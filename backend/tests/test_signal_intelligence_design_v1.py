from pathlib import Path


def test_signal_intelligence_design_v1_document_exists():
    assert _design_doc_path().is_file()


def test_signal_intelligence_design_v1_contains_required_sections():
    content = _design_doc_path().read_text()

    for section in (
        "## A. Purpose",
        "## B. Signal Taxonomy",
        "## C. Authority Boundaries",
        "## D. Data Flow",
        "## E. Future Integration Points",
        "## F. Risks",
    ):
        assert section in content


def _design_doc_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "signal_intelligence"
        / "signal_intelligence_design_v1.md"
    )
