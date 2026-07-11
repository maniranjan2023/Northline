"""
LongTermMemoryRepository
------------------------
Reads and writes long-term memories in Neon PostgreSQL + pgvector.
"""

from __future__ import annotations

import json

from psycopg_pool import ConnectionPool

from memory.models import MemoryRecord, MemoryType, RetrievedMemory


class LongTermMemoryRepository:
    """SQL repository for persistent user memories."""

    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def ensure_user(self, user_id: str) -> None:
        """Create user profile row if it does not exist."""
        with self.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )

    def insert(self, record: MemoryRecord, embedding: list[float], content_hash: str) -> str:
        """Insert one memory with its embedding vector."""
        embedding_literal = "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"

        with self.pool.connection() as conn:
            row = conn.execute(
                """
                INSERT INTO long_term_memories (
                    user_id, memory_type, content, metadata, importance,
                    embedding, content_hash
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s::vector, %s)
                RETURNING id::text
                """,
                (
                    record.user_id,
                    record.memory_type.value,
                    record.content,
                    json.dumps(record.metadata),
                    record.importance,
                    embedding_literal,
                    content_hash,
                ),
            ).fetchone()
        return row[0]

    def find_by_hash(self, user_id: str, content_hash: str) -> MemoryRecord | None:
        """Find an existing memory with the same content hash."""
        with self.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT id::text, user_id, memory_type, content, metadata, importance,
                       created_at, updated_at
                FROM long_term_memories
                WHERE user_id = %s AND content_hash = %s
                LIMIT 1
                """,
                (user_id, content_hash),
            ).fetchone()

        if not row:
            return None

        return MemoryRecord(
            id=row[0],
            user_id=row[1],
            memory_type=MemoryType(row[2]),
            content=row[3],
            metadata=row[4] or {},
            importance=row[5],
            created_at=row[6],
            updated_at=row[7],
        )

    def update_existing(self, record: MemoryRecord, content_hash: str, importance_boost: float = 0.1) -> None:
        """Update duplicate memory and slightly increase importance."""
        with self.pool.connection() as conn:
            conn.execute(
                """
                UPDATE long_term_memories
                SET importance = LEAST(1.0, importance + %s),
                    updated_at = NOW(),
                    metadata = metadata || %s::jsonb
                WHERE user_id = %s AND content_hash = %s
                """,
                (
                    importance_boost,
                    json.dumps(record.metadata),
                    record.user_id,
                    content_hash,
                ),
            )

    def search_by_embedding(
        self,
        user_id: str,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[RetrievedMemory]:
        """
        Semantic search using cosine distance in pgvector.

        Lower distance means more similar content.
        """
        embedding_literal = "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"

        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT id::text, user_id, memory_type, content, metadata, importance,
                       created_at, updated_at,
                       (embedding <=> %s::vector) AS distance
                FROM long_term_memories
                WHERE user_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding_literal, user_id, embedding_literal, top_k),
            ).fetchall()

        results: list[RetrievedMemory] = []
        for row in rows:
            distance = float(row[8])
            score = max(0.0, 1.0 - distance)
            results.append(
                RetrievedMemory(
                    record=MemoryRecord(
                        id=row[0],
                        user_id=row[1],
                        memory_type=MemoryType(row[2]),
                        content=row[3],
                        metadata=row[4] or {},
                        importance=row[5],
                        created_at=row[6],
                        updated_at=row[7],
                    ),
                    score=score,
                )
            )
        return results

    def list_recent(self, user_id: str, limit: int = 5) -> list[MemoryRecord]:
        """Fallback search when vector search is unavailable."""
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT id::text, user_id, memory_type, content, metadata, importance,
                       created_at, updated_at
                FROM long_term_memories
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            ).fetchall()

        return [
            MemoryRecord(
                id=row[0],
                user_id=row[1],
                memory_type=MemoryType(row[2]),
                content=row[3],
                metadata=row[4] or {},
                importance=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
            for row in rows
        ]

    def upsert_trip_plan(self, user_id: str, plan: dict, embedding: list[float], content_hash: str) -> None:
        """Store or replace the latest full trip plan snapshot for a user."""
        embedding_literal = "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"
        user_query = str(plan.get("user_query", "Trip plan"))
        content = f"Latest trip plan: {user_query}"

        with self.pool.connection() as conn:
            conn.execute(
                """
                DELETE FROM long_term_memories
                WHERE user_id = %s AND memory_type = %s
                """,
                (user_id, MemoryType.TRIP_PLAN.value),
            )
            conn.execute(
                """
                INSERT INTO long_term_memories (
                    user_id, memory_type, content, metadata, importance,
                    embedding, content_hash
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s::vector, %s)
                """,
                (
                    user_id,
                    MemoryType.TRIP_PLAN.value,
                    content,
                    json.dumps(plan),
                    1.0,
                    embedding_literal,
                    content_hash,
                ),
            )

    def get_latest_trip_plan(self, user_id: str) -> dict | None:
        """Return the most recent stored trip plan snapshot for a user."""
        with self.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT metadata
                FROM long_term_memories
                WHERE user_id = %s AND memory_type = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_id, MemoryType.TRIP_PLAN.value),
            ).fetchone()

        if not row or not row[0]:
            return None

        metadata = row[0]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        if not isinstance(metadata, dict) or not metadata.get("itinerary"):
            return None

        return metadata
