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
        safe_user = memory_manager.sanitize_user_id(user_id)
        items = await memory_manager.retrieve_memories(safe_user, query)
        from memory.profile_store import filter_semantic_memories, format_profile_block, get_profile, merge_memory_context

        user_profile = get_profile(safe_user)
        profile_block = format_profile_block(user_profile)
        if user_profile:
            filtered_texts = filter_semantic_memories([item.memory for item in items], user_profile)
            allowed = set(filtered_texts)
            items = [item for item in items if item.memory in allowed]
        memory_context = merge_memory_context(
            profile_block,
            memory_manager.format_memories_for_prompt(items),
        )
        preferences = {"profile": user_profile, "memories": [item.memory for item in items]}
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
