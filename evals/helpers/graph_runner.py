"""Run the Voyager LangGraph pipeline for eval cases."""

from __future__ import annotations

import uuid
from typing import Any

from deepeval.test_case import ToolCall

from main import (
    app,
    build_input_state,
    build_run_config,
    memory_manager,
    state_to_plan_dict,
)


def _unique_eval_ids(case_id: str) -> tuple[str, str]:
    """Isolate eval runs from real user checkpoints."""
    suffix = uuid.uuid4().hex[:8]
    user_id = f"eval_{case_id}_{suffix}"
    thread_id = memory_manager.build_thread_id(user_id)
    return user_id, thread_id


def run_trip_planning(
    user_query: str,
    case_id: str = "case",
    *,
    user_id: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """
    Invoke the full travel graph once and return final state + plan dict.

    Uses a throwaway eval user_id / thread_id so production checkpoints are untouched.
    Pass user_id/thread_id to reuse Mem0 identity across sessions in memory evals.
    """
    if not user_id or not thread_id:
        user_id, thread_id = _unique_eval_ids(case_id)
    config = build_run_config(
        user_id=user_id,
        session_id=thread_id,
        run_name=f"eval_{case_id}",
        tags=["eval", "nightly", case_id],
    )
    initial = build_input_state(user_query, user_id=user_id, session_id=thread_id)
    state = app.invoke(initial, config=config)
    plan = state_to_plan_dict(state) or {}
    return {
        "state": state,
        "plan": plan,
        "itinerary": state.get("itinerary", "") or plan.get("itinerary", ""),
        "user_id": user_id,
        "thread_id": thread_id,
    }


def extract_tool_calls(state: dict[str, Any]) -> list[ToolCall]:
    """
    Map graph state to MCP tool names for ToolCorrectnessMetric.

    Agents write raw MCP results under tool_outputs; we infer which tools ran.
    """
    tool_outputs = state.get("tool_outputs") or {}
    calls: list[ToolCall] = []

    if tool_outputs.get("research_agent") or tool_outputs.get("hotel_agent"):
        calls.append(ToolCall(name="tavily_search"))

    activity = tool_outputs.get("activity_agent") or {}
    if isinstance(activity, dict):
        if activity.get("weather") or activity.get("forecast"):
            calls.append(ToolCall(name="get_current_weather"))
            calls.append(ToolCall(name="get_forecast"))
        if activity.get("activities"):
            if not any(c.name == "tavily_search" for c in calls):
                calls.append(ToolCall(name="tavily_search"))

    flight = tool_outputs.get("flight_agent")
    if flight:
        calls.append(ToolCall(name="list_airports"))
        calls.append(ToolCall(name="list_airlines"))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[ToolCall] = []
    for call in calls:
        if call.name not in seen:
            seen.add(call.name)
            unique.append(call)
    return unique


def build_retrieval_context(plan: dict[str, Any], memory_snippet: str = "") -> list[str]:
    """Grounding context for Turn Faithfulness / Contextual Recall metrics."""
    chunks: list[str] = []
    if memory_snippet:
        chunks.append(memory_snippet)
    if plan.get("destination"):
        chunks.append(f"Destination: {plan['destination']}")
    if plan.get("itinerary"):
        chunks.append(str(plan["itinerary"])[:2000])
    if plan.get("hotel_results"):
        chunks.append(str(plan["hotel_results"])[:800])
    if plan.get("flight_results"):
        chunks.append(str(plan["flight_results"])[:800])
    return [c for c in chunks if c.strip()]
