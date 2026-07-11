-- Long-term memory tables for Voyager AI
-- Run once on Neon PostgreSQL

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    display_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS long_term_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES user_profiles(user_id),
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    importance REAL DEFAULT 0.5,
    embedding vector(384),
    content_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ltm_user_id ON long_term_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_ltm_type ON long_term_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_ltm_hash ON long_term_memories(user_id, content_hash);
