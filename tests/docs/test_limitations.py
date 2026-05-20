"""Guard rails for docs/LIMITATIONS.md (T17, Phase D lite seal)."""

from pathlib import Path

import pytest

DOC = Path(__file__).parent.parent.parent / "docs" / "LIMITATIONS.md"


@pytest.fixture(scope="module")
def text() -> str:
    assert DOC.exists(), f"LIMITATIONS.md missing at {DOC}"
    return DOC.read_text(encoding="utf-8")


def test_minimum_length(text: str) -> None:
    assert len(text.splitlines()) >= 85, "LIMITATIONS.md below Opus-register length floor"


def test_status_table_present(text: str) -> None:
    for field in ("| Status |", "| Date |", "| Owner |", "| Related |"):
        assert field in text, f"Status table missing field: {field}"


def test_seven_sections_present(text: str) -> None:
    for heading in (
        "## 1. Scope",
        "## 2. Evidence-Shape Limitations",
        "## 3. Operational Limitations",
        "## 4. Methodological Limitations",
        "## 5. Deployment Limitations",
        "## 6. When NOT to Use SIFTGuard",
        "## 7. Roadmap",
    ):
        assert heading in text, f"Section missing: {heading}"


def test_evidence_shape_anchors(text: str) -> None:
    for token in ("TEST-002", "SCHARDT", "0.000", "Volatility 3"):
        assert token in text, f"Evidence-shape anchor missing: {token}"


def test_operational_anchors(text: str) -> None:
    for token in ("UTM", "siftguard_cache", "5 GB"):
        assert token in text, f"Operational anchor missing: {token}"


def test_methodological_anchors(text: str) -> None:
    for token in ("text-match", "field-level", "ground truth"):
        assert token in text.lower(), f"Methodological anchor missing: {token}"


def test_deployment_anchors(text: str) -> None:
    for token in ("single-tenant", "localhost", "RBAC", "SIEM"):
        assert token in text, f"Deployment anchor missing: {token}"


def test_when_not_to_use_bullets(text: str) -> None:
    """The When-NOT section is the doc's portfolio center; each don't-use is explicit."""
    for token in (
        "live incident response",
        "multi-analyst",
        "real-time SOC",
        "sole authority",
    ):
        assert token in text, f"When-NOT bullet missing: {token}"


def test_cross_references(text: str) -> None:
    for ref in ("ADR-006", "ADR-007", "THREAT_MODEL"):
        assert ref in text, f"Cross-reference missing: {ref}"
    assert "generalization-gap" in text, "ADR-006 §generalization-gap citation missing"


def test_roadmap_named_items(text: str) -> None:
    """Roadmap items must reference upstream sources, not introduce new promises."""
    for token in ("row-chain", "field-level", "post-hackathon"):
        assert token in text.lower(), f"Roadmap pointer missing: {token}"
