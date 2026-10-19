-- Cloud Jobs store (cloud_jobs.db, SQLCipher via base.database). #827.
-- Applied idempotently; bump CLOUD_SCHEMA_VERSION and add a migration for changes.

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id             TEXT PRIMARY KEY,
    kind               TEXT NOT NULL,
    title              TEXT NOT NULL DEFAULT '',
    spec_json          TEXT NOT NULL,
    state              TEXT NOT NULL,
    outcome            TEXT,
    outcome_reason     TEXT NOT NULL DEFAULT '',
    cancel_request     TEXT,
    teardown_pending   INTEGER NOT NULL DEFAULT 0,
    capability_override INTEGER NOT NULL DEFAULT 0,
    attempts_used      INTEGER NOT NULL DEFAULT 0,
    fallback_used_json TEXT NOT NULL DEFAULT '[]',
    scheduled_at       REAL,
    created_at         REAL NOT NULL,
    updated_at         REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id       TEXT PRIMARY KEY,
    job_id           TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    attempt_no       INTEGER NOT NULL,
    provider         TEXT NOT NULL,
    region           TEXT NOT NULL DEFAULT '',
    mode             TEXT NOT NULL,
    idempotency_key  TEXT NOT NULL UNIQUE,
    shards_json      TEXT NOT NULL,
    submitted        INTEGER NOT NULL DEFAULT 0,
    submit_unknown   INTEGER NOT NULL DEFAULT 0,
    resources_json   TEXT NOT NULL DEFAULT '[]',
    teardown_done    INTEGER NOT NULL DEFAULT 0,
    cost_usd         REAL NOT NULL DEFAULT 0,
    started_at       REAL NOT NULL,
    ended_at         REAL,
    UNIQUE (job_id, attempt_no)
);
CREATE INDEX IF NOT EXISTS idx_attempts_job ON attempts(job_id);

CREATE TABLE IF NOT EXISTS shards (
    job_id        TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    idx           INTEGER NOT NULL,
    collected     INTEGER NOT NULL DEFAULT 0,
    failures      INTEGER NOT NULL DEFAULT 0,
    outputs_json  TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (job_id, idx)
);

-- Append-only; the UI reads only this. Pruned with its job.
CREATE TABLE IF NOT EXISTS job_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id    TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    ts        REAL NOT NULL,
    type      TEXT NOT NULL,
    data_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_job ON job_events(job_id, id);

-- Never pruned: monthly caps, calibration and Dashboards read it. No FK, so
-- rows outlive the jobs they describe.
CREATE TABLE IF NOT EXISTS spend_ledger (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id           TEXT NOT NULL,
    attempt_id       TEXT NOT NULL DEFAULT '',
    provider         TEXT NOT NULL,
    task             TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT '',
    kind             TEXT NOT NULL,          -- actual | estimate | reserved | billed
    amount_usd       REAL NOT NULL,
    duration_s       REAL NOT NULL DEFAULT 0,
    peak_rss_kib     REAL NOT NULL DEFAULT 0,
    peak_vcpu        REAL NOT NULL DEFAULT 0,
    peak_gpu         REAL NOT NULL DEFAULT 0,
    egress_bytes     INTEGER NOT NULL DEFAULT 0,
    ts               REAL NOT NULL,
    source           TEXT NOT NULL DEFAULT 'cloud_jobs'  -- cloud_jobs | poc
);
CREATE INDEX IF NOT EXISTS idx_ledger_ts ON spend_ledger(ts);
CREATE INDEX IF NOT EXISTS idx_ledger_job ON spend_ledger(job_id);

-- Risk rule overrides layered over the shipped YAML seed (#830).
CREATE TABLE IF NOT EXISTS risk_rules (
    rule_id     TEXT PRIMARY KEY,
    rule_json   TEXT NOT NULL,
    origin      TEXT NOT NULL,   -- seed | user
    updated_at  REAL NOT NULL
);
