from __future__ import annotations
import json
from pathlib import Path
from functools import lru_cache
from src.siftguard.eval.ground_truth import CaseManifest


CASES_DIR = Path("experiments/cases")


@lru_cache(maxsize=8)
def load_manifest(case_id: str) -> CaseManifest:
    path = CASES_DIR / case_id / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No manifest for case {case_id}: expected {path}")
    return CaseManifest.model_validate_json(path.read_text())