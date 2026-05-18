"""Atomic Panel 7 data.json updater.

Merges a single run's F1 into experiments/analysis/<case_id>/data.json under
panel_7.data.<agent_id>. Preserves all other panels. Last-write-wins per run timestamp.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_DIR = REPO_ROOT / "experiments" / "analysis"


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".panel7.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=False)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def update_panel_7(
    *,
    case_id: str,
    agent_id: str,
    f1: float | None,
    gt_version: str,
    applicable_count: int,
    not_applicable_count: int,
    run_timestamp: str | None = None,
) -> Path:
    data_path = ANALYSIS_DIR / case_id / "data.json"
    data: dict = {}
    if data_path.exists():
        try:
            data = json.loads(data_path.read_text())
        except json.JSONDecodeError:
            data = {}

    panel_7 = data.setdefault("panel_7", {"data": {}})
    panel_7_data = panel_7.setdefault("data", {})
    agent_block = panel_7_data.setdefault(agent_id, {"runs": [], "mean": None, "n": 0})

    ts = run_timestamp or datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    agent_block.setdefault("runs", []).append(
        {
            "f1": f1,
            "timestamp": ts,
            "gt_version": gt_version,
            "applicable_count": applicable_count,
            "not_applicable_count": not_applicable_count,
        }
    )

    scores = [r["f1"] for r in agent_block["runs"] if r.get("f1") is not None]
    agent_block["mean"] = (sum(scores) / len(scores)) if scores else None
    agent_block["n"] = len(scores)

    _atomic_write_json(data_path, data)
    return data_path
