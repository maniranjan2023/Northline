"""
MemoryManager
-------------
Single entry point for all memory operations.

Rule for the whole app:
- Agents and UI should call MemoryManager only.
- Do not read/write memory tables directly outside this class.
"""

from __future__ import annotations

from typing import Any

from memory.models import RetrievedMemory
from memory.services.embedding_service import EmbeddingService
from memory.services.long_term_service import LongTermMemoryService
from memory.services.short_term_service import ShortTermMemoryService
from memory.services.summarization_service import SummarizationService


class MemoryManager:
    """Facade that combines short-term and long-term memory behavior."""

    def __init__(self, llm, db_pool, embedding_service: EmbeddingService | None = None):
        self.short_term = ShortTermMemoryService()
        self.embedding = embedding_service or EmbeddingService()
        self.long_term = LongTermMemoryService(db_pool, self.embedding)
        self.summarizer = SummarizationService(llm)

    def build_thread_id(self, user_id: str) -> str:
        """
        Build short-term session id from username.

        Example: user_id='rahul' -> thread_id='rahul_chat'
        """
        safe_user = self._sanitize_user_id(user_id)
        return f"{safe_user}_chat"

    def prepare_session_state(
        self,
        user_query: str,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Load relevant long-term memories and create graph input state.

        Called before graph execution starts.
        """
        memories = self.long_term.retrieve_relevant(user_id=user_id, query=user_query)
        memory_context = self.format_memories_for_prompt(memories)
        return self.short_term.build_initial_state(
            user_query=user_query,
            user_id=user_id,
            session_id=session_id,
            memory_context=memory_context,
        )

    def load_memory_context(self, user_id: str, user_query: str) -> str:
        """Return only the memory text that agents can inject into prompts."""
        memories = self.long_term.retrieve_relevant(user_id=user_id, query=user_query)
        return self.format_memories_for_prompt(memories)

    def get_context_for_agent(self, state: dict[str, Any], agent_name: str) -> str:
        """Give an agent a small memory snippet for its prompt."""
        base = state.get("memory_context", "No prior memory found.")
        return f"Known user context:\n{base}\n\nCurrent agent: {agent_name}"

    def record_agent_result(
        self,
        state: dict[str, Any],
        agent_name: str,
        output: str,
        tool_output: Any | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Store one agent result in short-term state."""
        if error:
            patch = self.short_term.record_agent_error(agent_name, error)
        else:
            patch = self.short_term.record_agent_success(agent_name, output, tool_output)

        # Merge dictionaries because LangGraph uses reducer updates per key.
        merged_agent_outputs = dict(state.get("agent_outputs", {}))
        merged_tool_outputs = dict(state.get("tool_outputs", {}))
        merged_errors = dict(state.get("errors", {}))
        merged_retry = dict(state.get("retry_count", {}))

        merged_agent_outputs.update(patch.get("agent_outputs", {}))
        merged_tool_outputs.update(patch.get("tool_outputs", {}))
        merged_errors.update(patch.get("errors", {}))
        merged_retry.update(patch.get("retry_count", {}))

        return {
            "agent_outputs": merged_agent_outputs,
            "tool_outputs": merged_tool_outputs,
            "errors": merged_errors,
            "retry_count": merged_retry,
            "execution_status": patch.get("execution_status", "running"),
        }

    def persist_run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Save long-term memories after a successful run.

        Called once at the end of the graph.
        """
        records = self.summarizer.summarize_travel_run(state)
        self.long_term.store_records(records)
        self.save_trip_plan_from_state(state)
        return self.short_term.mark_completed()

    def save_trip_plan_from_state(self, state: dict[str, Any]) -> None:
        """Store a full trip snapshot for later follow-up questions."""
        user_id = state.get("user_id", "")
        itinerary = state.get("itinerary", "")
        if not user_id or not itinerary:
            return

        user_query = state.get("user_query", "")
        destination = state.get("destination", "")
        if not destination and user_query:
            try:
                from mcp_client import extract_destination

                destination = extract_destination(user_query)
            except Exception:
                destination = ""

        plan = {
            "user_query": user_query,
            "destination": destination,
            "flight_results": state.get("flight_results", ""),
            "hotel_results": state.get("hotel_results", ""),
            "weather_results": state.get("weather_results", ""),
            "itinerary": itinerary,
            "llm_calls": state.get("llm_calls", 0),
        }
        self.long_term.save_trip_plan(user_id, plan)

    def load_trip_plan(self, user_id: str) -> dict | None:
        """Load the latest trip plan saved for this user."""
        safe_user = self._sanitize_user_id(user_id)
        return self.long_term.load_trip_plan(safe_user)

    def format_memories_for_prompt(self, memories: list[RetrievedMemory]) -> str:
        """Convert retrieved memories into plain text for LLM prompts."""
        if not memories:
            return "No prior memory found for this user."

        lines = []
        for item in memories:
            lines.append(f"- [{item.record.memory_type.value}] {item.record.content}")
        return "\n".join(lines)

    def _sanitize_user_id(self, user_id: str) -> str:
        """Make username safe for ids and SQL keys."""
        clean = "".join(ch for ch in user_id.strip().lower() if ch.isalnum() or ch in {"_", "-"})
        return clean or "anonymous"
