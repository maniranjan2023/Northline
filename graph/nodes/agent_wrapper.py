"""Agent wrapper — records outputs into short-term checkpointed state."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from langchain_core.messages import AIMessage

from memory.memory_manager import MemoryManager

AGENT_OUTPUT_FIELDS = {
    "planner_agent": "planner_output",
    "research_agent": "research_output",
    "hotel_agent": "hotel_results",
    "flight_agent": "flight_results",
    "activity_agent": "activity_results",
    "final_response_agent": "itinerary",
}


def with_memory(
    agent_fn: Callable[[dict[str, Any]], dict[str, Any]],
    agent_name: str,
    memory_manager: MemoryManager,
):
    """Wrap sync agent nodes to record outputs in TravelState."""

    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        try:
            result = agent_fn(state)
            output_field = AGENT_OUTPUT_FIELDS[agent_name]
            output_value = str(result.get(output_field, ""))
            tool_output = result.get("tool_outputs", {}).get(agent_name)

            memory_patch = memory_manager.record_agent_result(
                state=state,
                agent_name=agent_name,
                output=output_value,
                tool_output=tool_output,
            )
            return {**result, **memory_patch}
        except Exception as exc:
            memory_patch = memory_manager.record_agent_result(
                state=state,
                agent_name=agent_name,
                output="",
                error=str(exc),
            )
            return {
                **memory_patch,
                "messages": [AIMessage(content=f"{agent_name} failed: {exc}")],
            }

    return wrapped
