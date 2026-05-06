"""Idempotent schema migrator for SIFTGuard.

Usage:
    python -m scripts.migrate --db audit/CASE-001.db
    python -m scripts.migrate --db audit/CASE-001.db --dry-run
    python -m scripts.migrate --db audit/CASE-001.db --verify

ADR: docs/adr/ADR-001-empirical-evaluation-framework.md
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "migrations"


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, "
        "applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "checksum TEXT NOT NULL)"
    )
    conn.commit()


def applied_versions(conn: sqlite3.Connection) -> dict[str, str]:
    cur = conn.execute("SELECT version, checksum FROM schema_migrations")
    return {row[0]: row[1] for row in cur.fetchall()}


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cur.fetchone() is not None


def split_sql_statements(sql: str) -> list[str]:
    """Strip comments + blank lines, split on semicolons."""
    cleaned = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        cleaned.append(line)
    body = "\n".join(cleaned)
    return [s.strip() for s in body.split(";") if s.strip()]


def apply_migration_001(conn: sqlite3.Connection, dry_run: bool = False) -> None:
    sql_path = MIGRATIONS_DIR / "001_eval_framework_schema.sql"
    statements = split_sql_statements(sql_path.read_text())

    alter_re = re.compile(r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)", re.IGNORECASE)

    for stmt in statements:
        m = alter_re.match(stmt)
        if m:
            table, col = m.group(1), m.group(2)
            if column_exists(conn, table, col):
                print(f"  [skip]  {table}.{col} already exists")
                continue
            print(f"  [apply] ALTER {table} ADD {col}")
            if not dry_run:
                conn.execute(stmt)
            continue

        # CREATE TABLE / CREATE INDEX — IF NOT EXISTS handles idempotency
        first_line = stmt.splitlines()[0].strip()
        print(f"  [apply] {first_line[:80]}")
        if not dry_run:
            conn.execute(stmt)

    if not dry_run:
        conn.commit()


def verify_migration_001(conn: sqlite3.Connection) -> bool:
    expected_columns = {
        "auditentry": [
            "tokens_in", "tokens_out", "cost_usd",
            "confidence_score", "correction_event",
        ],
    }
    expected_tables = [
        "iteration_snapshot",
        "hypothesis_event",
        "experiment_run",
        "schema_migrations",
    ]
    ok = True
    for table, cols in expected_columns.items():
        for col in cols:
            present = column_exists(conn, table, col)
            print(f"  [{'OK  ' if present else 'FAIL'}] {table}.{col}")
            ok = ok and present
    for t in expected_tables:
        present = table_exists(conn, t)
        print(f"  [{'OK  ' if present else 'FAIL'}] table {t}")
        ok = ok and present
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="SIFTGuard schema migrator")
    parser.add_argument("--db", required=True, help="Path to SQLite DB")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true",
                        help="Only verify schema, do not apply")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB does not exist: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    try:
        ensure_migrations_table(conn)

        if args.verify:
            print(f"Verifying schema in {db_path}")
            return 0 if verify_migration_001(conn) else 1

        applied = applied_versions(conn)
        sql_path = MIGRATIONS_DIR / "001_eval_framework_schema.sql"
        checksum = file_checksum(sql_path)

        if "001" in applied:
            if applied["001"] != checksum:
                print(f"  [WARN] migration 001 checksum drift")
                print(f"         applied:  {applied['001']}")
                print(f"         on-disk:  {checksum}")
                return 2
            print(f"  [skip]  migration 001 already applied (checksum match)")
            return 0

        print(f"Applying migration 001 to {db_path} (dry-run={args.dry_run})")
        apply_migration_001(conn, dry_run=args.dry_run)

        if not args.dry_run:
            conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                ("001", checksum),
            )
            conn.commit()
            print(f"  [done]  migration 001 recorded with checksum {checksum[:12]}...")
        else:
            print(f"  [dry-run] no changes committed")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())