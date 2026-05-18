"""Single source of truth for case discovery and manifest loading.

Replaces src/siftguard/eval/datasets/registry.py (deleted in ADR-008).
All callers import from here: get_case(), list_cases(), list_case_ids().
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from siftguard.eval.ground_truth import CaseManifest

CASES_DIR = Path(__file__).resolve().parents[3] / "experiments" / "cases"


@lru_cache(maxsize=16)
def get_case(case_id: str) -> CaseManifest:
    path = CASES_DIR / case_id / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No manifest for {case_id!r}: expected {path}")
    return CaseManifest.model_validate_json(path.read_text())


def list_case_ids() -> list[str]:
    if not CASES_DIR.exists():
        return []
    return sorted(p.name for p in CASES_DIR.iterdir() if (p / "manifest.json").exists())


def list_cases() -> list[CaseManifest]:
    return [get_case(cid) for cid in list_case_ids()]


def evidence_paths(manifest: CaseManifest) -> dict[str, Path]:
    """Returns {type: absolute_path} for all evidence files in manifest."""
    return {ef["type"]: Path(ef["path"]) for ef in manifest.evidence_files}


def evidence_available(manifest: CaseManifest) -> bool:
    return all(Path(ef["path"]).exists() for ef in manifest.evidence_files)


def ground_truth_path(manifest: CaseManifest) -> Path:
    return Path(manifest.ground_truth_path)
