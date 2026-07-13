"""Memory retrieval from long-term store (Mem0)."""

from __future__ import annotations

import logging

from memory.prompts import MEMORY_CONTEXT_HEADER
from memory.provider.base import BaseMemoryProvider, MemoryItem

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """Queries Mem0 and formats results for agent system prompts."""

    def __init__(self, provider: BaseMemoryProvider, top_k: int = 8):
        self._provider = provider
        self._top_k = top_k

    async def retrieve(self, user_id: str, query: str) -> list[MemoryItem]:
        """Retrieve relevant memories for a user query."""
        try:
            items = await self._provider.search(user_id, query, limit=self._top_k)
            logger.info(
                "Memory retrieval: user_id=%s query_len=%d results=%d",
                user_id,
                len(query),
                len(items),
            )
            return items
        except Exception as exc:
            logger.error("Memory retrieval failed for user_id=%s: %s", user_id, exc)
            return []

    def format_for_prompt(self, items: list[MemoryItem]) -> str:
        """Format memories as bullet list for system prompts."""
        if not items:
            return "No prior user information stored yet."

        bullets = "\n".join(f"- {item.memory}" for item in items if item.memory.strip())
        return MEMORY_CONTEXT_HEADER.format(memories=bullets).strip()

    def to_preferences(self, items: list[MemoryItem]) -> dict[str, list[str]]:
        """Lightweight structured view for state.user_preferences."""
        return {"memories": [item.memory for item in items if item.memory.strip()]}
