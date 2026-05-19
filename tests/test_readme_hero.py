"""T23: README hero structure validation.

The hero must (a) declare SIFTGuard as the project, (b) link to T22 tool
catalog, (c) link to ADR-006 (multi-orchestrator + vendor lock-in),
(d) embed at least one figure, (e) lead with multi-dataset numbers,
(f) carry the ADR-006 §5.2 cost-spread verbatim quote.
"""
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def _read() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_exists() -> None:
    assert README.exists(), "README.md missing at repo root"


def test_h1_is_siftguard() -> None:
    first = _read().splitlines()[0].strip()
    assert first == "# SIFTGuard", f"unexpected H1: {first!r}"


def test_links_tool_catalog() -> None:
    assert "docs/TOOL_CATALOG.md" in _read(), \
        "README must link to TOOL_CATALOG.md (T22)"


def test_links_adr_006() -> None:
    text = _read()
    assert "ADR-006" in text, "README must reference ADR-006"
    assert "docs/adr/ADR-006-multi-orchestrator-vendor-lockin.md" in text, \
        "README must link to the ADR-006 file"


def test_embeds_at_least_one_figure() -> None:
    text = _read()
    assert "](docs/figures/" in text or "](docs/architecture/" in text, \
        "README must embed at least one figure from docs/figures or docs/architecture"


def test_hero_leads_with_multi_dataset_numbers() -> None:
    """First ~120 lines must carry TEST-001 and TEST-002 evidence, not just architecture prose."""
    head = "\n".join(_read().splitlines()[:120])
    assert "TEST-001" in head, "Hero must reference TEST-001 (memory dataset)"
    assert "TEST-002" in head, "Hero must reference TEST-002 (disk dataset)"


def test_hero_quotes_adr_006_cost_spread() -> None:
    """ADR-006 §5.2 verbatim per T10 flag — 2.72x cost spread is the empirical knockout."""
    assert "2.72×" in _read(), \
        "Hero must quote ADR-006 §5.2 cost-spread number (2.72×)"


def test_hero_names_all_five_orchestrators() -> None:
    text = _read()
    for name in ("Native Loop", "LangGraph", "OpenAI FC", "Gemini", "Claude Code"):
        assert name in text, f"hero must name orchestrator: {name}"