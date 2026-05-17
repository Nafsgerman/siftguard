#!/usr/bin/env python3
"""
Seed 3 blocked mutation receipts into the audit DB so Panel 8 renders authentic data.
Usage: python3 scripts/seed_spoliation_receipts.py [--db PATH]
"""
import argparse
import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from siftguard.agent.instrumentation import SnapshotWriter  # noqa: E402

RECEIPTS = [
    {
        "case_id": "TEST-001",
        "attempted_action": "DELETE FROM iteration_snapshot WHERE experiment_run_id=1",
        "reason": "DELETE operation rejected: iteration_snapshot is append-only per ADR-007",
        "actor": "external-sql-client",
    },
    {
        "case_id": "TEST-001",
        "attempted_action": "UPDATE hypothesis_event SET event_type='hypothesis_confirmed' WHERE id=3",
        "reason": "UPDATE operation rejected: hypothesis_event is append-only per ADR-007",
        "actor": "external-sql-client",
    },
    {
        "case_id": "TEST-001",
        "attempted_action": "DROP TABLE blocked_mutation",
        "reason": "Schema modification rejected: audit tables are immutable per ADR-007",
        "actor": "external-sql-client",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed spoliation receipts")
    parser.add_argument(
        "--db",
        default="/cases/TEST-001/siftguard.db",
        help="Path to the SIFTGuard audit SQLite DB",
    )
    args = parser.parse_args()

    writer = SnapshotWriter(db_path=args.db)
    receipt_ids = []

    for receipt in RECEIPTS:
        rid = writer.emit_blocked_mutation(
            case_id=receipt["case_id"],
            attempted_action=receipt["attempted_action"],
            reason=receipt["reason"],
            actor=receipt["actor"],
        )
        receipt_ids.append(rid)
        print(f"  ✓ blocked_mutation receipt: {rid}")
        print(f"    action : {receipt['attempted_action'][:72]}...")

    print(f"\nSeeded {len(receipt_ids)} receipts into {args.db}")


if __name__ == "__main__":
    main()