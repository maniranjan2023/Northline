"""
memory_save_node
----------------
Runs at the end of the graph.

What it does:
1. Summarizes the completed run
2. Stores structured long-term memories
3. Marks short-term execution as completed
"""

from __future__ import annotations

from typing import Any

from memory.memory_manager import MemoryManager


def memory_save_node(state: dict[str, Any], memory_manager: MemoryManager) -> dict[str, Any]:
    return memory_manager.persist_run(state)
