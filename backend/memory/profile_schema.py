"""PostgreSQL schema for structured user profile attributes."""

from __future__ import annotations

PROFILE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_profile (
    user_id TEXT NOT NULL,
    attribute_key TEXT NOT NULL,
    attribute_value TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'user',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, attribute_key)
);

CREATE INDEX IF NOT EXISTS idx_user_profile_user_id ON user_profile(user_id);
"""


def setup_profile_schema(pool) -> None:
    statements = [stmt.strip() for stmt in PROFILE_SCHEMA_SQL.split(";") if stmt.strip()]
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
