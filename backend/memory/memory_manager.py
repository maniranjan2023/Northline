"""
MemoryManager — single facade for short-term + long-term memory.

Short-term: LangGraph PostgresSaver (thread_id) — handled by graph checkpointer.
Long-term: Mem0 (user_id) — handled by this manager.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage

from memory.config import MemoryConfig
from memory.extractor import MemoryExtractor
from memory.profile_store import (
    filter_semantic_memories,
    format_profile_block,
    get_profile,
    merge_memory_context,
)
from memory.provider.base import BaseMemoryProvider, MemoryItem
from memory.provider.mem0_provider import Mem0Provider
from memory.retriever import MemoryRetriever

logger = logging.getLogger(__name__)


class MemoryManager:
    """Production memory facade — inject into graph nodes, never instantiate Mem0 in nodes."""

    def __init__(
        self,
        llm,
        provider: BaseMemoryProvider | None = None,
        config: MemoryConfig | None = None,
    ):
        self._config = config or MemoryConfig.from_env()
        self._provider = provider or Mem0Provider(self._config)
        self._retriever = MemoryRetriever(self._provider, top_k=self._config.memory_top_k)
        self._extractor = MemoryExtractor(llm, self._provider)

    @property
    def config(self) -> MemoryConfig:
        return self._config

    def build_thread_id(self, user_id: str, trip_slug: str | None = None) -> str:
        """
        Build short-term session id.

        Examples:
          user_id='rahul' -> 'rahul_chat' (default session)
          user_id='rahul', trip_slug='tokyo' -> 'rahul_trip_tokyo'
        """
        safe_user = self.sanitize_user_id(user_id)
        if trip_slug:
            safe_slug = "".join(ch for ch in trip_slug.strip().lower() if ch.isalnum() or ch in {"_", "-"})
            return f"{safe_user}_trip_{safe_slug}" if safe_slug else f"{safe_user}_chat"
        return f"{safe_user}_chat"

    def sanitize_user_id(self, user_id: str) -> str:
        clean = "".join(ch for ch in user_id.strip().lower() if ch.isalnum() or ch in {"_", "-"})
        return clean or "anonymous"

    def build_initial_state(self, user_query: str, user_id: str, thread_id: str) -> dict[str, Any]:
        """
        Create graph input state WITHOUT long-term memory.

        RetrieveMemoryNode loads Mem0 context on graph start.
        """
        safe_user = self.sanitize_user_id(user_id)
        return {
            "messages": [HumanMessage(content=user_query)],
            "user_query": user_query,
            "user_id": safe_user,
            "thread_id": thread_id,
            "planner_output": "",
            "research_output": "",
            "hotel_results": "",
            "flight_results": "",
            "activity_results": "",
            "itinerary": "",
            "selected_hotels": [],
            "selected_flights": [],
            "activities": [],
            "destination": "",
            "memory_context": "",
            "user_preferences": {},
            "tool_outputs": {},
            "agent_outputs": {},
            "errors": {},
            "current_step": "start",
            "llm_calls": 0,
            "quality_passed": False,
            "quality_issues": [],
            "revision_count": 0,
            "revision_hints": "",
            "lesson_context": "",
            "lessons_loaded": [],
            "review_summary": {},
        }

    async def retrieve_memories(self, user_id: str, query: str) -> list[MemoryItem]:
        """Retrieve relevant Mem0 memories for a user + query."""
        safe_user = self.sanitize_user_id(user_id)
        return await self._retriever.retrieve(safe_user, query)

    async def load_memory_context(self, user_id: str, query: str) -> str:
        """Formatted memory block for prompts (profile + Mem0 semantic search)."""
        safe_user = self.sanitize_user_id(user_id)
        profile = get_profile(safe_user)
        profile_block = format_profile_block(profile)

        items = await self.retrieve_memories(safe_user, query)
        if profile:
            filtered_texts = set(filter_semantic_memories([item.memory for item in items], profile))
            items = [item for item in items if item.memory in filtered_texts]

        semantic_block = self._retriever.format_for_prompt(items)
        return merge_memory_context(profile_block, semantic_block)

    async def load_profile_context(self, user_id: str) -> str:
        """Structured profile block only — no Mem0 search."""
        safe_user = self.sanitize_user_id(user_id)
        return format_profile_block(get_profile(safe_user))

    def format_memories_for_prompt(self, items: list[MemoryItem]) -> str:
        return self._retriever.format_for_prompt(items)

    async def save_memory(self, user_id: str, conversation: dict[str, str]) -> int:
        """
        Extract and store durable facts from a conversation turn.

        conversation keys: user_message, assistant_response, planner_output (optional)
        """
        safe_user = self.sanitize_user_id(user_id)
        return await self._extractor.save_conversation(
            safe_user,
            user_message=conversation.get("user_message", ""),
            assistant_response=conversation.get("assistant_response", ""),
            planner_output=conversation.get("planner_output", ""),
        )

    async def save_explicit_correction(self, user_id: str, correction_text: str) -> int:
        """Persist a user-stated correction immediately for future trips."""
        clean_text = " ".join((correction_text or "").split())
        if not clean_text:
            return 0
        safe_user = self.sanitize_user_id(user_id)
        await self._provider.add_fact(safe_user, f"User correction: {clean_text}")
        return 1

    async def search_memories(self, user_id: str, query: str, *, limit: int | None = None) -> list[MemoryItem]:
        safe_user = self.sanitize_user_id(user_id)
        return await self._provider.search(safe_user, query, limit=limit or self._config.memory_top_k)

    async def delete_memory(self, memory_id: str) -> None:
        await self._provider.delete(memory_id)

    async def update_memory(self, memory_id: str, text: str) -> None:
        await self._provider.update(memory_id, text)

    def record_agent_result(
        self,
        state: dict[str, Any],
        agent_name: str,
        output: str,
        tool_output: Any | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Track agent output in short-term checkpointed state."""
        merged_agent_outputs = dict(state.get("agent_outputs", {}))
        merged_tool_outputs = dict(state.get("tool_outputs", {}))
        merged_errors = dict(state.get("errors", {}))

        if error:
            merged_errors[agent_name] = error
        else:
            merged_agent_outputs[agent_name] = output
            if tool_output is not None:
                merged_tool_outputs[agent_name] = tool_output

        return {
            "agent_outputs": merged_agent_outputs,
            "tool_outputs": merged_tool_outputs,
            "errors": merged_errors,
            "current_step": agent_name if not error else f"{agent_name}_error",
        }

    def system_prompt_with_memory(self, base_prompt: str, memory_context: str) -> str:
        """Inject known user information into an agent system prompt."""
        if not memory_context or memory_context.startswith("No prior"):
            return base_prompt
        return f"{base_prompt.strip()}\n\n{memory_context}"
