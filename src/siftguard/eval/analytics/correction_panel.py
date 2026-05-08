import sqlite3
from collections import Counter
from typing import Any

from siftguard.models.correction_taxonomy import SelfCorrectionType, SelfCorrectionEvent, classify_correction


def get_correction_breakdown(db_path: str, case_id: str) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, agent_iteration, tool_name, correction_event
        FROM auditentry
        WHERE case_id = ? AND correction_event IS NOT NULL
        ORDER BY agent_iteration ASC
    """, (case_id,))
    rows = cur.fetchall()
    conn.close()

    events: list[SelfCorrectionEvent] = []
    for row in rows:
        raw_msg = row["correction_event"] or ""
        events.append(SelfCorrectionEvent(
            audit_id=row["id"],
            event_type=classify_correction(raw_msg),
            iteration=row["agent_iteration"] or 0,
            tool_name=row["tool_name"],
            message=raw_msg,
        ))

    type_counts = Counter(e.event_type.value for e in events)
    by_iteration: dict[int, list[str]] = {}
    for e in events:
        by_iteration.setdefault(e.iteration, []).append(e.event_type.value)

    return {
        "total_corrections": len(events),
        "breakdown_by_type": dict(type_counts),
        "breakdown_by_iteration": {str(k): v for k, v in sorted(by_iteration.items())},
        "events": [e.model_dump() for e in events],
        "unknown_pct": round(
            type_counts.get(SelfCorrectionType.UNKNOWN, 0) / max(len(events), 1) * 100, 1
        ),
    }