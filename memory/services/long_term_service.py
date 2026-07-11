"""
LongTermMemoryService
---------------------
Stores and retrieves persistent user memories with semantic search.
"""

from __future__ import annotations

import os

from memory.models import MemoryRecord, RetrievedMemory
from memory.repositories.long_term_repository import LongTermMemoryRepository
from memory.services.embedding_service import EmbeddingService


class LongTermMemoryService:
    """Business logic for long-term memory."""

    def __init__(self, pool, embedding_service: EmbeddingService):
        self.repo = LongTermMemoryRepository(pool)
        self.embedding = embedding_service
        self.duplicate_threshold = float(os.getenv("MEMORY_DUPLICATE_THRESHOLD", "0.92"))
        self.default_top_k = int(os.getenv("MEMORY_TOP_K", "5"))

    def retrieve_relevant(self, user_id: str, query: str, top_k: int | None = None) -> list[RetrievedMemory]:
        """
        Find memories that are most relevant to the current user message.

        Steps:
        1. Embed the query
        2. Search pgvector
        3. Rank by similarity + importance
        """
        top_k = top_k or self.default_top_k
        self.repo.ensure_user(user_id)

        try:
            query_embedding = self.embedding.embed(query)
            candidates = self.repo.search_by_embedding(user_id, query_embedding, top_k=top_k * 2)
            ranked = self._rank_memories(candidates)
            return ranked[:top_k]
        except Exception:
            # If pgvector is not ready yet, use recent memories as fallback.
            recent = self.repo.list_recent(user_id, limit=top_k)
            return [
                RetrievedMemory(record=record, score=record.importance)
                for record in recent
            ]

    def store_records(self, records: list[MemoryRecord]) -> int:
        """
        Save structured memories.

        Returns number of newly inserted memories.
        """
        inserted = 0
        for record in records:
            self.repo.ensure_user(record.user_id)
            content_hash = self.embedding.content_hash(record.content)
            duplicate = self._find_near_duplicate(record, content_hash)

            if duplicate:
                self.repo.update_existing(record, content_hash)
                continue

            embedding = self.embedding.embed(record.content)
            self.repo.insert(record, embedding, content_hash)
            inserted += 1
        return inserted

    def _find_near_duplicate(self, record: MemoryRecord, content_hash: str) -> bool:
        """Detect exact or very similar existing memory."""
        existing = self.repo.find_by_hash(record.user_id, content_hash)
        if existing:
            return True

        try:
            query_embedding = self.embedding.embed(record.content)
            similar = self.repo.search_by_embedding(record.user_id, query_embedding, top_k=1)
            if similar and similar[0].score >= self.duplicate_threshold:
                return True
        except Exception:
            return False

        return False

    def _rank_memories(self, memories: list[RetrievedMemory]) -> list[RetrievedMemory]:
        """
        Rank by combined score:
        semantic similarity + stored importance.
        """

        def rank_key(item: RetrievedMemory) -> float:
            return (item.score * 0.7) + (item.record.importance * 0.3)

        return sorted(memories, key=rank_key, reverse=True)

    def save_trip_plan(self, user_id: str, plan: dict) -> None:
        """Persist the latest full trip plan for follow-up questions."""
        if not plan.get("itinerary"):
            return

        self.repo.ensure_user(user_id)
        summary_text = f"Trip plan: {plan.get('user_query', 'travel plan')}"
        content_hash = self.embedding.content_hash(summary_text)
        embedding = self.embedding.embed(summary_text)
        self.repo.upsert_trip_plan(user_id, plan, embedding, content_hash)

    def load_trip_plan(self, user_id: str) -> dict | None:
        """Load the latest stored trip plan snapshot for a user."""
        self.repo.ensure_user(user_id)
        return self.repo.get_latest_trip_plan(user_id)
