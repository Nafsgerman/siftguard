-- Migration 002: Add run_id to auditentry for experiment tracking
-- ADR: docs/adr/ADR-004-loop-instrumentation.md
-- Idempotency: handled by scripts/migrate.py column-existence check
-- Existing rows get NULL run_id (v1 runs that predate the framework — correct)

ALTER TABLE auditentry ADD COLUMN run_id TEXT;
CREATE INDEX IF NOT EXISTS ix_auditentry_run_id ON auditentry (run_id);
