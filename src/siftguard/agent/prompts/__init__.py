"""Prompt loader for SIFTGuard agent.

Versions:
  v1              — original free-form prompt (baseline, ablation reference)
  v1_training     — v1 + training annotations
  v2              — structured-confidence JSON output (eval framework default)
  v2_training     — v2 + training_annotation field per finding
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent

_VALID_VERSIONS = {"v1", "v1_training", "v2", "v2_training"}


@lru_cache(maxsize=8)
def load_prompt(version: str = "v2") -> str:
    if version not in _VALID_VERSIONS:
        raise ValueError(
            f"Unknown prompt version {version!r}. "
            f"Valid: {sorted(_VALID_VERSIONS)}"
        )
    path = _PROMPTS_DIR / f"{version}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def available_versions() -> list[str]:
    return sorted(_VALID_VERSIONS)