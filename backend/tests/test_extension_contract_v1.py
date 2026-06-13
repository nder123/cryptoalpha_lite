from pathlib import Path


def test_extension_contract_v1_document_exists():
    assert _extension_contract_path().is_file()


def test_extension_contract_v1_contains_required_sections():
    content = _extension_contract_path().read_text()

    assert "## A. Frozen Core" in content
    assert "## B. Allowed Future Extensions" in content
    assert "## C. Forbidden Extensions" in content
    assert "## D. Upgrade Path" in content


def test_extension_contract_v1_names_frozen_core_components():
    content = _extension_contract_path().read_text()

    for component in (
        "ContractRegistry",
        "ValidationCore",
        "ValidationCore._merge()",
        "CONTRACT_RULES",
        "event_lineage",
        "event_contract",
        "Architecture authority map",
    ):
        assert component in content


def test_extension_contract_v1_names_allowed_extensions():
    content = _extension_contract_path().read_text()

    for extension in (
        "Signal scoring layer",
        "Regime classification layer",
        "Observability enrichment",
        "Strategy layer",
        "PnL analytics layer",
    ):
        assert extension in content


def test_extension_contract_v1_names_forbidden_extensions():
    content = _extension_contract_path().read_text()

    for forbidden_pattern in (
        "Second decision owner",
        "Contract interpreter duplication",
        "Lineage-driven decision authority",
        "Cross-module mutation of `allowed`",
        "Runtime override of `ValidationCore._merge()`",
    ):
        assert forbidden_pattern in content


def test_extension_contract_v1_names_upgrade_path():
    content = _extension_contract_path().read_text()

    assert "v2 = validation infrastructure (current)" in content
    assert "v3 = signal intelligence" in content
    assert "v4 = strategy layer" in content
    assert "v5 = production trading layer" in content


def _extension_contract_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "controlled_pilot"
        / "EXTENSION_CONTRACT_V1.md"
    )
