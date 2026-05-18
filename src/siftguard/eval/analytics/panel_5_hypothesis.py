"""Panel 5 — Hypothesis evolution timeline.

Claim: The agent revises beliefs in light of evidence — observable as a time series.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib.axes

from siftguard.eval.analytics.load_traces import get_db_path, load_experiment_runs_from_db
from siftguard.eval.analytics.style import (
    BLUE,
    GRAY,
    GREEN,
    RED,
    YELLOW,
    add_claim,
    apply_style,
    placeholder,
)

CLAIM = "The agent forms, revises, and confirms hypotheses in light of evidence — belief evolution is observable."
EVENT_COLORS = {
    "formed": BLUE,
    "updated": YELLOW,
    "confirmed": GREEN,
    "abandoned": RED,
}
EVENT_MARKERS = {"formed": "o", "updated": "s", "confirmed": "*", "abandoned": "X"}


def _load_hypothesis_events(db_path: Path, run_id: str) -> list[dict]:
    events = []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM hypothesis_event WHERE run_id=? ORDER BY id",
            (run_id,),
        )
        for row in cur.fetchall():
            events.append(dict(row))
        conn.close()
    except Exception:
        pass
    return events


def render(ax: matplotlib.axes.Axes, case_id: str = "TEST-001") -> dict:
    apply_style()
    db_path = get_db_path(case_id)

    if not db_path.exists():
        placeholder(ax, "Panel 5 — Hypothesis Evolution", f"DB not found: {db_path}")
        return {"status": "placeholder"}

    runs = load_experiment_runs_from_db(db_path)
    baseline = next(
        (
            r
            for r in runs
            if json.loads(r.get("config_json") or "{}")
            .get("notes", "")
            .startswith("Primary baseline")
        ),
        runs[0] if runs else None,
    )

    if not baseline:
        placeholder(ax, "Panel 5 — Hypothesis Evolution", "No runs found.")
        return {"status": "placeholder"}

    run_id = baseline["run_id"]
    events = _load_hypothesis_events(db_path, run_id)

    if not events:
        placeholder(
            ax,
            "Panel 5 — Hypothesis Evolution",
            "No hypothesis events recorded.\n"
            "v1 fallback runs do not emit hypothesis events.\n"
            "Re-run baseline with fixed v2 prompt to populate this panel.",
        )
        return {"status": "placeholder"}

    hyp_ids = list({e["hypothesis_id"] for e in events})
    hyp_index = {hid: i for i, hid in enumerate(hyp_ids)}

    for event in events:
        hid = event["hypothesis_id"]
        y = hyp_index[hid]
        x = event["iteration"]
        etype = event["event_type"]
        conf = event.get("confidence") or 0.5
        color = EVENT_COLORS.get(etype, GRAY)
        marker = EVENT_MARKERS.get(etype, "o")
        ax.scatter(x, y + conf * 0.8, c=color, marker=marker, s=80, zorder=3, alpha=0.85)

    for etype, color in EVENT_COLORS.items():
        ax.scatter([], [], c=color, marker=EVENT_MARKERS[etype], label=etype, s=60)

    ax.set_yticks(range(len(hyp_ids)))
    ax.set_yticklabels([hid[:20] for hid in hyp_ids], fontsize=7)
    ax.set_title("Panel 5 — Hypothesis Evolution Timeline", fontweight="bold")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Hypothesis (y offset = confidence)")
    ax.legend(loc="upper right", fontsize=7)
    add_claim(ax, CLAIM)

    return {"status": "ok", "run_id": run_id, "n_events": len(events)}
