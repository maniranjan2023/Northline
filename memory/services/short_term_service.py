"""
ShortTermMemoryService
----------------------
Handles session-only memory inside LangGraph state.

Short-term memory lives only for the current thread/session.
It is saved automatically by the Postgres checkpointer.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage


class ShortTermMemoryService:
    """Builds and updates in-session graph state."""

    def build_initial_state(
        self,
        user_query: str,
        user_id: str,
        session_id: str,
        memory_context: str = "",
    ) -> dict[str, Any]:
        """
        Create the starting state for one graph run.

        user_id  -> long-term memory key (username)
        session_id -> short-term memory key (thread_id)
        """
        return {
            "messages": [HumanMessage(content=user_query)],
            "user_query": user_query,
            "flight_results": "",
            "hotel_results": "",
            "weather_results": "",
            "itinerary": "",
            "llm_calls": 0,
            "user_id": user_id,
            "session_id": session_id,
            "current_task": user_query,
            "tool_outputs": {},
            "agent_outputs": {},
            "errors": {},
            "retry_count": {},
            "memory_context": memory_context,
            "execution_status": "running",
        }

    def record_agent_success(
        self,
        agent_name: str,
        output: str,
        tool_output: Any | None = None,
    ) -> dict[str, Any]:
        """Save one agent result into short-term state."""
        patch: dict[str, Any] = {
            "agent_outputs": {agent_name: output},
            "execution_status": "running",
        }
        if tool_output is not None:
            patch["tool_outputs"] = {agent_name: tool_output}
        return patch

    def record_agent_error(self, agent_name: str, error_message: str) -> dict[str, Any]:
        """Track an agent failure and increase retry count."""
        return {
            "errors": {agent_name: error_message},
            "retry_count": {agent_name: 1},
            "execution_status": "running",
        }

    def mark_completed(self) -> dict[str, Any]:
        """Mark the session as successfully completed."""
        return {"execution_status": "completed"}

    def mark_failed(self) -> dict[str, Any]:
        """Mark the session as failed."""
        return {"execution_status": "failed"}
