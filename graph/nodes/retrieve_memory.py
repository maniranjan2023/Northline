"""Retrieve long-term memories from Mem0 before agents run."""

from __future__ import annotations

import asyncio
import logging

from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


async def _retrieve(state: dict, memory_manager: MemoryManager) -> dict:
    user_id = state.get("user_id", "")
    query = state.get("user_query", "")

    if not user_id or not query:
        logger.warning("RetrieveMemoryNode: missing user_id or query")
        return {
            "memory_context": "No prior user information stored yet.",
            "user_preferences": {},
            "current_step": "retrieve_memory",
        }

    try:
        items = await memory_manager.retrieve_memories(user_id, query)
        memory_context = memory_manager.format_memories_for_prompt(items)
        preferences = {"memories": [item.memory for item in items]}
        logger.info("RetrieveMemoryNode: user_id=%s memories=%d", user_id, len(items))
        return {
            "memory_context": memory_context,
            "user_preferences": preferences,
            "current_step": "retrieve_memory",
        }
    except Exception as exc:
        logger.error("RetrieveMemoryNode failed (continuing without memory): %s", exc)
        return {
            "memory_context": "No prior user information stored yet.",
            "user_preferences": {},
            "current_step": "retrieve_memory",
        }


def retrieve_memory_node(state: dict, memory_manager: MemoryManager) -> dict:
    """Sync LangGraph node — runs Mem0 retrieval via asyncio.run."""
    return asyncio.run(_retrieve(state, memory_manager))
