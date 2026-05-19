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


def apply_migration(
    conn: sqlite3.Connection,
    version: str,
    sql_path: Path,
    dry_run: bool = False,
) -> None:
    alter_re = re.compile(r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)", re.IGNORECASE)
    statements = split_sql_statements(sql_path.read_text())
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
        first_line = stmt.splitlines()[0].strip()
        print(f"  [apply] {first_line[:80]}")
        if not dry_run:
            conn.execute(stmt)
    if not dry_run:
        conn.commit()


# Keep explicit function for backwards compat with test imports
def apply_migration_001(conn: sqlite3.Connection, dry_run: bool = False) -> None:
    apply_migration(conn, "001", MIGRATIONS_DIR / "001_eval_framework_schema.sql", dry_run)


def verify_migration_001(conn: sqlite3.Connection) -> bool:
    expected_columns = {
        "auditentry": [
            "tokens_in",
            "tokens_out",
            "cost_usd",
            "confidence_score",
            "correction_event",
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


def verify_migration_002(conn: sqlite3.Connection) -> bool:
    present = column_exists(conn, "auditentry", "run_id")
    print(f"  [{'OK  ' if present else 'FAIL'}] auditentry.run_id")
    return present


def verify_migration_003(conn: sqlite3.Connection) -> bool:
    present = table_exists(conn, "blocked_mutation")
    print(f"  [{'OK  ' if present else 'FAIL'}] table blocked_mutation")
    return present


MIGRATIONS = [
    ("001", "001_eval_framework_schema.sql", verify_migration_001),
    ("002", "002_run_id.sql", verify_migration_002),
    ("003", "003_blocked_mutation.sql", verify_migration_003),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="SIFTGuard schema migrator")
    parser.add_argument("--db", required=True, help="Path to SQLite DB")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true", help="Only verify schema, do not apply")
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
            ok = True
            for _version, _filename, verify_fn in MIGRATIONS:
                ok = verify_fn(conn) and ok
            return 0 if ok else 1

        applied = applied_versions(conn)

        for version, filename, _verify_fn in MIGRATIONS:
            sql_path = MIGRATIONS_DIR / filename
            if not sql_path.exists():
                print(f"  [skip]  migration {version} — file not found: {filename}")
                continue

            checksum = file_checksum(sql_path)

            if version in applied:
                if applied[version] != checksum:
                    print(f"  [WARN] migration {version} checksum drift")
                    print(f"         applied:  {applied[version]}")
                    print(f"         on-disk:  {checksum}")
                    return 2
                print(f"  [skip]  migration {version} already applied (checksum match)")
                continue

            print(f"Applying migration {version} to {db_path} (dry-run={args.dry_run})")
            apply_migration(conn, version, sql_path, dry_run=args.dry_run)

            if not args.dry_run:
                conn.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                    (version, checksum),
                )
                conn.commit()
                print(f"  [done]  migration {version} recorded with checksum {checksum[:12]}...")
            else:
                print("  [dry-run] no changes committed")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
