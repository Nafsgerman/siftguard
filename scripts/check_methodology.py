"""Fail-fast check that EVAL_FRAMEWORK.md sha matches the constant in code.

Run: python -m scripts.check_methodology
Exit 0 if matched, 1 otherwise.
"""

from __future__ import annotations

import sys

from siftguard.eval.methodology import (
    METHODOLOGY_DOC_NAME,
    METHODOLOGY_DOC_SHA256,
    METHODOLOGY_VERSION,
    _compute_doc_sha256,
    doc_path,
)


def main() -> int:
    live_sha = _compute_doc_sha256(doc_path())
    if live_sha != METHODOLOGY_DOC_SHA256:
        print(
            f"FAIL methodology drift\n"
            f"  doc:      {METHODOLOGY_DOC_NAME}\n"
            f"  declared: {METHODOLOGY_DOC_SHA256}\n"
            f"  on disk:  {live_sha}\n"
            f"  action:   bump METHODOLOGY_VERSION and update METHODOLOGY_DOC_SHA256, "
            f"or revert {METHODOLOGY_DOC_NAME}.",
            file=sys.stderr,
        )
        return 1
    print(f"OK methodology v{METHODOLOGY_VERSION} sha={METHODOLOGY_DOC_SHA256[:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
