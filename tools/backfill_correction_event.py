"""Backfill auditentry.correction_event for rows where the previous iteration had failures.

Pure SQL transform over existing data. Idempotent: only updates rows where
correction_event IS NULL. Safe to re-run.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BACKFILL_SQL = """
WITH iter_outcomes AS (
    SELECT
        run_id,
        agent_iteration,
        MAX(CASE WHEN outcome = 'fail' THEN 1 ELSE 0 END) AS had_fail
    FROM auditentry
    GROUP BY run_id, agent_iteration
),
recovery_rows AS (
    SELECT a.id
    FROM auditentry a
    JOIN iter_outcomes prev
        ON prev.run_id = a.run_id
       AND prev.agent_iteration = a.agent_iteration - 1
    WHERE a.correction_event IS NULL
      AND prev.had_fail = 1
)
UPDATE auditentry
SET correction_event = 'tool_failure_recovery'
WHERE id IN (SELECT id FROM recovery_rows);
"""

PREVIEW_SQL = """
SELECT
    a.id,
    a.run_id,
    a.agent_iteration,
    a.tool_name,
    a.outcome,
    a.correction_event AS current_value
FROM auditentry a
JOIN (
    SELECT run_id, agent_iteration,
           MAX(CASE WHEN outcome = 'fail' THEN 1 ELSE 0 END) AS had_fail
    FROM auditentry GROUP BY run_id, agent_iteration
) prev
    ON prev.run_id = a.run_id
   AND prev.agent_iteration = a.agent_iteration - 1
WHERE a.correction_event IS NULL
  AND prev.had_fail = 1
ORDER BY a.run_id, a.id;
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Execute UPDATE (default: dry-run)")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERROR: db not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(PREVIEW_SQL).fetchall()
    print(f"Candidates: {len(rows)}")
    print(f"{'id':<5} {'iter':<5} {'tool':<22} {'outcome':<8} {'current':<10}")
    for r in rows:
        print(
            f"{r['id']:<5} {r['agent_iteration']:<5} {r['tool_name']:<22} {r['outcome']:<8} {str(r['current_value']):<10}"
        )

    if not args.apply:
        print("\nDry-run. Re-run with --apply to commit.")
        return 0

    cur = conn.execute(BACKFILL_SQL)
    conn.commit()
    print(f"\nApplied. Rows updated: {cur.rowcount}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
