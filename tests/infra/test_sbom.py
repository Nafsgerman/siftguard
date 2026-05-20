"""T21: SBOM exists, is valid SPDX JSON, and contains core dependencies."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SBOM = REPO_ROOT / "sbom.spdx.json"


def test_sbom_exists() -> None:
    assert SBOM.exists(), (
        "sbom.spdx.json missing — run: syft scan dir:. -o spdx-json > sbom.spdx.json"
    )


def test_sbom_valid_json() -> None:
    data = json.loads(SBOM.read_text())
    assert isinstance(data, dict)


def test_sbom_contains_core_deps() -> None:
    data = json.loads(SBOM.read_text())
    names = {p.get("name", "").lower() for p in data.get("packages", [])}
    for dep in ("anthropic", "fastapi", "pydantic"):
        assert dep in names, f"Core dep '{dep}' missing from SBOM; found: {sorted(names)[:15]}"


def test_sbom_spdx_version() -> None:
    data = json.loads(SBOM.read_text())
    assert "spdxVersion" in data, "Not a valid SPDX document"
