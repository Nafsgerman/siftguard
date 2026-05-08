"""Single source of truth for evaluation methodology version.

Any artifact (manifest.json, report.md, ADR) that claims to follow this
methodology MUST embed the block returned by `current_block()`. The SHA256
of EVAL_FRAMEWORK.md is computed at import time so doc edits force a
version bump or an explicit checksum update.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

# Update both fields together. CI asserts these match the live doc.
METHODOLOGY_VERSION = "1.0.0"
METHODOLOGY_DOC_NAME = "EVAL_FRAMEWORK.md"

# Project root resolution: this file lives at src/siftguard/eval/methodology.py
# Root is 3 parents up: eval -> siftguard -> src -> <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOC_PATH = _REPO_ROOT / METHODOLOGY_DOC_NAME


class MethodologyDocMissing(RuntimeError):
    """Raised when EVAL_FRAMEWORK.md cannot be located at import-time."""


def _compute_doc_sha256(path: Path) -> str:
    if not path.is_file():
        raise MethodologyDocMissing(
            f"Methodology document not found at {path}. "
            f"Cannot stamp artifacts without an immutable reference."
        )
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


METHODOLOGY_DOC_SHA256 = _compute_doc_sha256(_DOC_PATH)


@dataclass(frozen=True)
class MethodologyBlock:
    """Immutable identity of the methodology used to produce an artifact."""

    version: str
    doc: str
    doc_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown_header(self) -> str:
        """Render as a fenced metadata block for report.md headers."""
        return (
            "<!-- methodology -->\n"
            f"**Methodology:** v{self.version} "
            f"([{self.doc}](./{self.doc}) · "
            f"`sha256:{self.doc_sha256[:12]}…`)\n"
        )


def current_block() -> MethodologyBlock:
    return MethodologyBlock(
        version=METHODOLOGY_VERSION,
        doc=METHODOLOGY_DOC_NAME,
        doc_sha256=METHODOLOGY_DOC_SHA256,
    )


def doc_path() -> Path:
    return _DOC_PATH