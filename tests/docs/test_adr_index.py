"""T15: ADR index integrity.

After the T15 ADR-007 reslot (spoliation moat) and ADR-009 rename
(scorer-audit-db moved off the 007 slot), assert:

1. No two ADR files share a number.
2. ADR-007 is the spoliation-moat ADR (referenced by README hero + RELEASE_NOTES).
3. ADR-009 is the scorer source ADR (renamed from old ADR-007).
4. All public-facing ADR links in README + RELEASE_NOTES resolve to existing files.
5. ADR-003 (loop instrumentation) carries the substantive Opus rewrite.
6. No stale `ADR-007 (scorer)` reference survives in README or dashboard.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs" / "adr"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_duplicate_adr_numbers() -> None:
    numbers: list[str] = []
    for f in ADR_DIR.glob("ADR-*.md"):
        m = re.match(r"ADR-(\d{3})-", f.name)
        if m:
            numbers.append(m.group(1))
    assert len(numbers) == len(set(numbers)), f"Duplicate ADR numbers: {numbers}"


def test_adr_007_is_spoliation_moat() -> None:
    f = ADR_DIR / "ADR-007-spoliation-moat.md"
    assert f.exists(), "ADR-007-spoliation-moat.md missing (T15 deliverable)"
    body = _read(f)
    assert body.splitlines()[0].startswith("# ADR-007"), "ADR-007 title prefix wrong"
    assert "spoliation" in body.lower(), "ADR-007 must discuss spoliation"
    assert "append-only" in body.lower(), "ADR-007 must reference append-only DB"
    assert "scorer" not in body.splitlines()[0].lower(), "ADR-007 title must not say 'scorer'"


def test_adr_009_is_scorer_source() -> None:
    f = ADR_DIR / "ADR-009-scorer-audit-db.md"
    assert f.exists(), "ADR-009-scorer-audit-db.md missing (renamed from ADR-007)"
    body = _read(f)
    assert body.splitlines()[0].startswith("# ADR-009"), "ADR-009 title prefix wrong"
    assert "scorer" in body.lower(), "ADR-009 must discuss the scorer"


def test_old_adr_007_scorer_filename_is_gone() -> None:
    f = ADR_DIR / "ADR-007-scorer-audit-db.md"
    assert not f.exists(), "Old ADR-007-scorer-audit-db.md must be renamed to ADR-009"


def test_readme_hero_link_resolves() -> None:
    readme = _read(REPO_ROOT / "README.md")
    assert "docs/adr/ADR-007-spoliation-moat.md" in readme
    assert (ADR_DIR / "ADR-007-spoliation-moat.md").exists()


def test_release_notes_adr_links_resolve() -> None:
    rn = _read(REPO_ROOT / "docs" / "RELEASE_NOTES.md")
    for match in re.findall(r"docs/adr/(ADR-\d{3}-[a-z0-9-]+\.md)", rn):
        assert (ADR_DIR / match).exists(), f"Broken ADR link in RELEASE_NOTES.md: {match}"


def test_adr_003_substantive_rewrite() -> None:
    f = ADR_DIR / "ADR-003-loop-instrumentation.md"
    assert f.exists()
    body = _read(f)
    line_count = len(body.splitlines())
    assert line_count > 100, (
        f"ADR-003 expected substantial post-Opus rewrite; got {line_count} lines"
    )
    for keyword in (
        "SnapshotWriter",
        "hypothesis_event",
        "iteration_snapshot",
        "ADR-006",
        "ADR-007",
    ):
        assert keyword in body, f"ADR-003 missing keyword: {keyword}"


def test_no_stale_adr_007_scorer_reference_in_readme() -> None:
    readme = _read(REPO_ROOT / "README.md")
    assert "The audit-DB scorer interface is defined (ADR-009)" in readme
    assert "audit-DB scorer interface is defined (ADR-007)" not in readme


def test_no_stale_adr_007_scorer_reference_in_dashboard() -> None:
    dash = _read(REPO_ROOT / "src" / "siftguard" / "dashboard" / "index.html")
    assert "Scorer running in report-text fallback mode — ADR-007" not in dash
    assert "ADR-007 — resolve in T15" not in dash
