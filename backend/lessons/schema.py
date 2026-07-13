"""PostgreSQL schema for the lesson book."""

from __future__ import annotations

LESSON_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lessons (
    lesson_id UUID PRIMARY KEY,
    lesson TEXT NOT NULL,
    category VARCHAR(64) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.2,
    times_seen INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    destination TEXT,
    trip_type TEXT,
    budget_tier TEXT,
    travel_style TEXT,
    season TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lesson_evidence (
    evidence_id UUID PRIMARY KEY,
    lesson_id UUID NOT NULL REFERENCES lessons(lesson_id) ON DELETE CASCADE,
    problem TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    observation TEXT NOT NULL,
    run_id TEXT,
    destination TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS candidate_lessons (
    candidate_id UUID PRIMARY KEY,
    suggested_lesson TEXT NOT NULL,
    category VARCHAR(64) NOT NULL,
    problem TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    source VARCHAR(32) NOT NULL,
    run_id TEXT,
    user_query TEXT,
    times_seen INTEGER NOT NULL DEFAULT 1,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.2,
    status VARCHAR(32) NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS improvement_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    run_id TEXT,
    thread_id TEXT,
    user_id TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lessons_category ON lessons(category);
CREATE INDEX IF NOT EXISTS idx_lessons_destination ON lessons(destination);
CREATE INDEX IF NOT EXISTS idx_lessons_confidence ON lessons(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_lessons_status ON candidate_lessons(status);
CREATE INDEX IF NOT EXISTS idx_improvement_events_run_id ON improvement_events(run_id);
"""


def setup_lesson_schema(pool) -> None:
    statements = [stmt.strip() for stmt in LESSON_SCHEMA_SQL.split(";") if stmt.strip()]
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
