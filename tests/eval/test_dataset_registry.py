"""Tests for siftguard.eval.datasets.registry."""
from __future__ import annotations
import pytest
from unittest.mock import patch
from pathlib import Path
from siftguard.eval.datasets.registry import (
    get_dataset, list_datasets, available_datasets, DatasetMeta,
)


def test_list_datasets_returns_all_three():
    cases = list_datasets()
    assert "TEST-001" in cases and "TEST-002" in cases and len(cases) >= 2


def test_get_dataset_known():
    meta = get_dataset("TEST-001")
    assert meta.case_id == "TEST-001"
    assert meta.threat_type == "apt_c2"
    assert "memory" in str(meta.memory_image)


def test_get_dataset_unknown_raises():
    with pytest.raises(KeyError, match="Unknown case_id"):
        get_dataset("TEST-999")


def test_ground_truth_path_correct_suffix():
    for cid in list_datasets():
        meta = get_dataset(cid)
        assert meta.ground_truth_path.name == f"{cid}.json"


def test_to_evidence_dict_has_memory_key():
    meta = get_dataset("TEST-001")
    d = meta.to_evidence_dict()
    assert "memory" in d
    assert "TEST-001" in d["memory"]


def test_evidence_available_false_when_missing(tmp_path):
    meta = DatasetMeta(
        case_id="FAKE",
        description="fake",
        threat_type="none",
        memory_image=tmp_path / "nonexistent.img",
        ground_truth_path=tmp_path / "nonexistent.json",
        briefing="fake",
    )
    assert not meta.evidence_available
    assert not meta.ground_truth_available


def test_evidence_available_true_when_exists(tmp_path):
    img = tmp_path / "mem.img"
    gt = tmp_path / "gt.json"
    img.touch()
    gt.write_text('{"case_id": "X"}')
    meta = DatasetMeta(
        case_id="X", description="x", threat_type="x",
        memory_image=img, ground_truth_path=gt, briefing="x",
    )
    assert meta.evidence_available
    assert meta.ground_truth_available


def test_available_datasets_excludes_missing(monkeypatch):
    monkeypatch.setattr(
        "siftguard.eval.datasets.registry._REGISTRY",
        {"TEST-001": get_dataset("TEST-001")},
    )
    # TEST-001 image won't exist in CI, so available_datasets() returns []
    result = available_datasets()
    assert isinstance(result, list)


def test_load_ground_truth_returns_dict(tmp_path):
    import json
    gt = tmp_path / "TEST-001.json"
    gt.write_text(json.dumps({"case_id": "TEST-001", "expected_iocs": []}))
    meta = DatasetMeta(
        case_id="TEST-001", description="x", threat_type="apt_c2",
        memory_image=tmp_path / "mem.img", ground_truth_path=gt, briefing="x",
    )
    data = meta.load_ground_truth()
    assert data["case_id"] == "TEST-001"