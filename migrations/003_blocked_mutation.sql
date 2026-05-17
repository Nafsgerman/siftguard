CREATE TABLE IF NOT EXISTS blocked_mutation (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id       TEXT    NOT NULL UNIQUE,
    case_id          TEXT    NOT NULL,
    attempted_action TEXT    NOT NULL,
    reason           TEXT    NOT NULL,
    actor            TEXT    NOT NULL DEFAULT 'siftguard-agent',
    timestamp        TEXT    NOT NULL
);
