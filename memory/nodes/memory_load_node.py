"""
memory_load_node
----------------
Runs at the start of the graph.

What it does:
1. Reads user_id and user_query from state
2. Retrieves relevant long-term memories
3. Puts them into state['memory_context']
"""

from __future__ import annotations

from typing import Any

from memory.memory_manager import MemoryManager


def memory_load_node(state: dict[str, Any], memory_manager: MemoryManager) -> dict[str, Any]:
    user_id = state.get("user_id", "anonymous")
    user_query = state.get("user_query", "")

    # If context already exists (resume), keep it.
    if state.get("memory_context"):
        return {"execution_status": "running"}

    memory_context = memory_manager.load_memory_context(user_id=user_id, query=user_query)
    return {
        "memory_context": memory_context,
        "execution_status": "running",
    }
