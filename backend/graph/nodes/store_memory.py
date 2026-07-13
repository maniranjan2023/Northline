"""Store durable user facts to Mem0 after the final response."""

from __future__ import annotations

import asyncio
import logging

from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


async def _store(state: dict, memory_manager: MemoryManager) -> dict:
    user_id = state.get("user_id", "")
    user_message = state.get("user_query", "")
    assistant_response = state.get("itinerary", "")
    planner_output = state.get("planner_output", "")

    if not user_id or not user_message or not assistant_response:
        logger.info("StoreMemoryNode: skipped (missing user_id, query, or itinerary)")
        return {"current_step": "store_memory"}

    try:
        stored = await memory_manager.save_memory(
            user_id,
            {
                "user_message": user_message,
                "assistant_response": assistant_response,
                "planner_output": planner_output,
            },
        )
        logger.info("StoreMemoryNode: user_id=%s stored_facts=%d", user_id, stored)
    except Exception as exc:
        logger.error("StoreMemoryNode failed (graph continues): %s", exc)

    return {"current_step": "store_memory"}


def store_memory_node(state: dict, memory_manager: MemoryManager) -> dict:
    """Sync LangGraph node — runs Mem0 save via asyncio.run."""
    return asyncio.run(_store(state, memory_manager))
