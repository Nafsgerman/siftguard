"""T24: Devpost SUBMISSION.md drift guard.

The Devpost submission must (a) carry the README hero tagline verbatim,
(b) quote ADR-006 §5.2 cost-spread number (2.72×), (c) name all five
orchestrators, (d) reference both TEST-001 and TEST-002, (e) state
12/12 spoliation, (f) not reference dropped TEST-004 / TEST-005.
"""

from pathlib import Path

SUB = Path(__file__).resolve().parents[1] / "docs" / "devpost" / "SUBMISSION.md"


def _read() -> str:
    return SUB.read_text(encoding="utf-8")


def test_submission_exists() -> None:
    assert SUB.exists(), "docs/devpost/SUBMISSION.md missing"


def test_tagline_matches_readme_hero() -> None:
    tagline = (
        "Court-defensible autonomous DFIR. Five orchestrators on one "
        "typed MCP server. Real F1 measured across two public forensics datasets."
    )
    assert tagline in _read(), "tagline must match README hero subtitle verbatim"


def test_quotes_adr_006_cost_spread() -> None:
    assert "2.72×" in _read(), "must quote ADR-006 §5.2 cost-spread (2.72×)"


def test_names_all_five_orchestrators() -> None:
    text = _read()
    for name in ("OpenAI FC", "Native Loop", "Claude Code", "LangGraph", "Gemini 3 Pro"):
        assert name in text, f"submission must name orchestrator: {name}"


def test_references_both_datasets() -> None:
    text = _read()
    assert "TEST-001" in text and "TEST-002" in text


def test_spoliation_12_of_12() -> None:
    assert "12/12" in _read()


def test_no_dropped_test_cases() -> None:
    text = _read()
    for dropped in ("TEST-004", "TEST-005"):
        assert (
            dropped not in text
        ), f"{dropped} is permanently dropped per ship list — must not appear"


def test_evaluation_methodology_linked() -> None:
    assert "EVAL_FRAMEWORK.md" in _read()


def test_limitations_linked() -> None:
    assert "LIMITATIONS.md" in _read()


def test_no_broken_adr_007_link() -> None:
    """ADR-007 file currently missing (T15 scope); do not link from submission."""
    assert (
        "ADR-007" not in _read()
    ), "ADR-007 file does not exist yet — do not reference until T15 lands"
