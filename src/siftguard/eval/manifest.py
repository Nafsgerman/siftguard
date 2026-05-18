"""Manifest helpers — attach methodology block to experiment manifests.

Idempotent: calling attach_to_manifest twice produces the same result.
Strict: refuses to overwrite a methodology block with a different version.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .methodology import MethodologyBlock, current_block


class MethodologyMismatch(RuntimeError):
    """Raised when a manifest already has a different methodology block."""


def attach_to_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Stamp the current methodology block onto a manifest dict in place.

    Returns the same dict for chaining. Does not write to disk.
    """
    block = current_block()
    existing = manifest.get("methodology")
    if existing is not None:
        if (
            existing.get("version") != block.version
            or existing.get("doc_sha256") != block.doc_sha256
        ):
            raise MethodologyMismatch(
                f"Manifest already pinned to methodology "
                f"v{existing.get('version')} sha={existing.get('doc_sha256', '?')[:12]}…; "
                f"current is v{block.version} sha={block.doc_sha256[:12]}…. "
                f"Refusing to silently overwrite."
            )
        return manifest
    manifest["methodology"] = block.to_dict()
    return manifest


def stamp_manifest_file(path: Path) -> MethodologyBlock:
    """Read a manifest.json from disk, stamp it, write it back atomically.

    Returns the methodology block that was stamped.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"manifest root must be an object, got {type(data).__name__}")
    attach_to_manifest(data)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)
    return current_block()
