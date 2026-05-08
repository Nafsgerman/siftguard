import json
import pytest
from pathlib import Path

from siftguard.eval.methodology import (
    METHODOLOGY_VERSION,
    METHODOLOGY_DOC_NAME,
    METHODOLOGY_DOC_SHA256,
    current_block,
    doc_path,
)
from siftguard.eval.manifest import (
    attach_to_manifest,
    stamp_manifest_file,
    MethodologyMismatch,
)


def test_doc_exists_and_sha_is_64_hex():
    assert doc_path().is_file()
    assert len(METHODOLOGY_DOC_SHA256) == 64
    int(METHODOLOGY_DOC_SHA256, 16)  # raises if not hex


def test_block_is_frozen_and_complete():
    b = current_block()
    assert b.version == METHODOLOGY_VERSION
    assert b.doc == METHODOLOGY_DOC_NAME
    assert b.doc_sha256 == METHODOLOGY_DOC_SHA256
    with pytest.raises(Exception):
        b.version = "9.9.9"  # frozen dataclass


def test_markdown_header_contains_version_and_short_sha():
    md = current_block().to_markdown_header()
    assert f"v{METHODOLOGY_VERSION}" in md
    assert METHODOLOGY_DOC_SHA256[:12] in md
    assert METHODOLOGY_DOC_NAME in md


def test_attach_to_manifest_stamps_block():
    m = {"runs": []}
    out = attach_to_manifest(m)
    assert out is m
    assert m["methodology"]["version"] == METHODOLOGY_VERSION
    assert m["methodology"]["doc_sha256"] == METHODOLOGY_DOC_SHA256


def test_attach_is_idempotent():
    m = {"runs": []}
    attach_to_manifest(m)
    snapshot = dict(m["methodology"])
    attach_to_manifest(m)
    assert m["methodology"] == snapshot


def test_attach_rejects_mismatch():
    m = {"methodology": {"version": "0.0.1", "doc": "X.md", "doc_sha256": "00" * 32}}
    with pytest.raises(MethodologyMismatch):
        attach_to_manifest(m)


def test_stamp_manifest_file_round_trips(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"runs": [{"id": "R1"}]}))
    block = stamp_manifest_file(path)
    data = json.loads(path.read_text())
    assert data["methodology"] == block.to_dict()
    assert data["runs"] == [{"id": "R1"}]
    # second stamp is a no-op
    stamp_manifest_file(path)
    assert json.loads(path.read_text()) == data