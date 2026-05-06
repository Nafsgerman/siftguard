-- Migration 001: Empirical Evaluation Framework schema additions
-- ADR: docs/adr/ADR-001-empirical-evaluation-framework.md
-- Date: 2026-05-06
-- Idempotency: handled by scripts/migrate.py (column-existence checks for ALTERs)
-- Reversibility: ALTER additions are nullable; tables are independent and droppable

-- ============================================================
-- 1. auditentry column additions (additive, nullable, safe)
-- ============================================================
ALTER TABLE auditentry ADD COLUMN tokens_in INTEGER;
ALTER TABLE auditentry ADD COLUMN tokens_out INTEGER;
ALTER TABLE auditentry ADD COLUMN cost_usd REAL;
ALTER TABLE auditentry ADD COLUMN confidence_score REAL;
ALTER TABLE auditentry ADD COLUMN correction_event TEXT;

-- ============================================================
-- 2. iteration_snapshot — state at each iteration boundary
-- ============================================================
CREATE TABLE IF NOT EXISTS iteration_snapshot (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                TEXT NOT NULL,
    case_id               TEXT NOT NULL,
    iteration             INTEGER NOT NULL,
    findings_json         TEXT NOT NULL,
    iocs_json             TEXT NOT NULL,
    hypotheses_json       TEXT NOT NULL,
    cumulative_tokens_in  INTEGER NOT NULL DEFAULT 0,
    cumulative_tokens_out INTEGER NOT NULL DEFAULT 0,
    cumulative_cost_usd   REAL NOT NULL DEFAULT 0.0,
    wall_time_ms          INTEGER NOT NULL,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, iteration)
);

CREATE INDEX IF NOT EXISTS ix_iteration_snapshot_run_id  ON iteration_snapshot (run_id);
CREATE INDEX IF NOT EXISTS ix_iteration_snapshot_case_id ON iteration_snapshot (case_id);

-- ============================================================
-- 3. hypothesis_event — Bayesian belief evolution
-- ============================================================
CREATE TABLE IF NOT EXISTS hypothesis_event (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    case_id       TEXT NOT NULL,
    iteration     INTEGER NOT NULL,
    event_type    TEXT NOT NULL
        CHECK (event_type IN ('formed', 'updated', 'confirmed', 'abandoned')),
    hypothesis_id TEXT NOT NULL,
    content       TEXT NOT NULL,
    confidence    REAL
        CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_hypothesis_event_run_id    ON hypothesis_event (run_id);
CREATE INDEX IF NOT EXISTS ix_hypothesis_event_iteration ON hypothesis_event (iteration);

-- ============================================================
-- 4. experiment_run — top-level record per agent invocation
-- ============================================================
CREATE TABLE IF NOT EXISTS experiment_run (
    run_id               TEXT PRIMARY KEY,
    case_id              TEXT NOT NULL,
    agent_id             TEXT NOT NULL,
    config_json          TEXT NOT NULL,
    ground_truth_path    TEXT,
    final_score          REAL,
    completed_iterations INTEGER,
    terminated_reason    TEXT
        CHECK (terminated_reason IS NULL OR terminated_reason IN
            ('verdict_reached', 'max_iterations', 'error', 'aborted')),
    total_tokens_in      INTEGER NOT NULL DEFAULT 0,
    total_tokens_out     INTEGER NOT NULL DEFAULT 0,
    total_cost_usd       REAL NOT NULL DEFAULT 0.0,
    started_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at         DATETIME
);

CREATE INDEX IF NOT EXISTS ix_experiment_run_case_id  ON experiment_run (case_id);
CREATE INDEX IF NOT EXISTS ix_experiment_run_agent_id ON experiment_run (agent_id);

-- ============================================================
-- 5. schema_migrations — track which migrations applied
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    checksum   TEXT NOT NULL
);