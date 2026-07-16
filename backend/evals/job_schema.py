"""PostgreSQL schema for eval jobs + latest suite results (shared web/worker)."""

from __future__ import annotations

EVAL_JOB_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS eval_jobs (
    job_id TEXT PRIMARY KEY,
    suite VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    source VARCHAR(32) NOT NULL DEFAULT 'inngest',
    inngest_run_id TEXT,
    progress JSONB NOT NULL DEFAULT '{}'::jsonb,
    log_tail TEXT NOT NULL DEFAULT '',
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS eval_suite_results (
    suite VARCHAR(32) PRIMARY KEY,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_jobs_status ON eval_jobs(status);
CREATE INDEX IF NOT EXISTS idx_eval_jobs_created_at ON eval_jobs(created_at DESC);
"""


def setup_eval_job_schema(pool) -> None:
    statements = [stmt.strip() for stmt in EVAL_JOB_SCHEMA_SQL.split(";") if stmt.strip()]
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
