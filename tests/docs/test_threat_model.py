"""Guard rails for docs/THREAT_MODEL.md (T16, Phase D lite)."""

from pathlib import Path

import pytest

DOC = Path(__file__).parent.parent.parent / "docs" / "THREAT_MODEL.md"


@pytest.fixture(scope="module")
def text() -> str:
    assert DOC.exists(), f"THREAT_MODEL.md missing at {DOC}"
    return DOC.read_text(encoding="utf-8")


def test_minimum_length(text: str) -> None:
    assert len(text.splitlines()) >= 150


def test_status_table_present(text: str) -> None:
    for field in ("| Status |", "| Date |", "| Owner |", "| Framework |", "| Related |"):
        assert field in text, f"Status table missing field: {field}"


def test_stride_section_six_categories(text: str) -> None:
    assert "## 2. STRIDE Analysis" in text
    for category in (
        "**Spoofing**",
        "**Tampering**",
        "**Repudiation**",
        "**Information Disclosure**",
        "**Denial of Service**",
        "**Elevation of Privilege**",
    ):
        assert category in text, f"STRIDE category missing: {category}"


def test_agent_specific_section_five_threats(text: str) -> None:
    assert "## 3. Agent-Specific Threats" in text
    for heading in (
        "### 3.1 Prompt Injection via Evidence Contents",
        "### 3.2 Tool Exfiltration via MCP",
        "### 3.3 Model Jailbreak",
        "### 3.4 Audit-Trail Tampering",
        "### 3.5 Hallucinated IOCs",
    ):
        assert heading in text, f"Agent-specific threat missing: {heading}"


def test_adr_cross_references(text: str) -> None:
    for adr in ("ADR-001", "ADR-002", "ADR-003", "ADR-006", "ADR-007"):
        assert adr in text, f"Cross-reference missing: {adr}"


def test_threat_to_control_map(text: str) -> None:
    assert "## 4. Threat-to-Control Map" in text
    assert "| Threat | Primary Control | Secondary Control |" in text


def test_out_of_scope_section(text: str) -> None:
    assert "## 5. Out of Scope" in text
    for boundary in ("Multi-tenant", "Network-exposed", "Supply-chain", "Side-channel"):
        assert boundary in text, f"Out-of-scope boundary missing: {boundary}"


def test_references_footer(text: str) -> None:
    assert "## 6. References" in text
    assert "tests/spoliation/" in text
    assert "LIMITATIONS.md" in text


def test_no_new_unsupported_claims(text: str) -> None:
    for token in ("SQLite trigger", "chain hash", "field-level provenance"):
        assert token in text, f"Post-hackathon hardening item not named: {token}"
    assert "post-hackathon" in text.lower()
