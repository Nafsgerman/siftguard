"""Tests for atomic Panel 7 data.json writer."""

from __future__ import annotations

import json

from siftguard.eval import panel_7_writer


def test_creates_skeleton(tmp_path, monkeypatch):
    monkeypatch.setattr(panel_7_writer, "ANALYSIS_DIR", tmp_path)
    p = panel_7_writer.update_panel_7(
        case_id="TEST-X",
        agent_id="siftguard-v2",
        f1=0.8,
        gt_version="1.1.0",
        applicable_count=5,
        not_applicable_count=2,
        run_timestamp="20260515_120000",
    )
    data = json.loads(p.read_text())
    assert data["panel_7"]["data"]["siftguard-v2"]["mean"] == 0.8
    assert data["panel_7"]["data"]["siftguard-v2"]["n"] == 1


def test_preserves_other_panels(tmp_path, monkeypatch):
    monkeypatch.setattr(panel_7_writer, "ANALYSIS_DIR", tmp_path)
    (tmp_path / "TEST-X").mkdir()
    (tmp_path / "TEST-X" / "data.json").write_text(
        json.dumps(
            {
                "panel_1": {"existing": True},
                "panel_7": {
                    "data": {
                        "siftguard-v2": {
                            "runs": [{"f1": 0.6, "timestamp": "old"}],
                            "mean": 0.6,
                            "n": 1,
                        }
                    }
                },
            }
        )
    )
    panel_7_writer.update_panel_7(
        case_id="TEST-X",
        agent_id="siftguard-v2",
        f1=0.8,
        gt_version="1.1.0",
        applicable_count=5,
        not_applicable_count=0,
        run_timestamp="20260515_130000",
    )
    data = json.loads((tmp_path / "TEST-X" / "data.json").read_text())
    assert data["panel_1"]["existing"] is True
    block = data["panel_7"]["data"]["siftguard-v2"]
    assert len(block["runs"]) == 2
    assert abs(block["mean"] - 0.7) < 1e-9
    assert block["n"] == 2


def test_none_f1_skipped_from_mean(tmp_path, monkeypatch):
    monkeypatch.setattr(panel_7_writer, "ANALYSIS_DIR", tmp_path)
    panel_7_writer.update_panel_7(
        case_id="TEST-X",
        agent_id="x",
        f1=None,
        gt_version="1.1.0",
        applicable_count=0,
        not_applicable_count=3,
        run_timestamp="t1",
    )
    panel_7_writer.update_panel_7(
        case_id="TEST-X",
        agent_id="x",
        f1=0.5,
        gt_version="1.1.0",
        applicable_count=2,
        not_applicable_count=0,
        run_timestamp="t2",
    )
    data = json.loads((tmp_path / "TEST-X" / "data.json").read_text())
    block = data["panel_7"]["data"]["x"]
    assert block["mean"] == 0.5 and block["n"] == 1
    assert len(block["runs"]) == 2
