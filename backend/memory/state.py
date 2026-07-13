"""TravelState — graph state persisted by PostgresSaver per thread_id."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict
import operator

from langchain_core.messages import AnyMessage


class TravelState(TypedDict, total=False):
    """
    Full graph state checkpointed after every node.

    Short-term scope: thread_id (one conversation session)
    Long-term scope: user_id (Mem0, across sessions)
    """

    # Conversation
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str

    # Agent outputs
    planner_output: str
    research_output: str
    hotel_results: str
    flight_results: str
    activity_results: str
    itinerary: str

    # Structured selections (optional enrichment)
    selected_hotels: list[str]
    selected_flights: list[str]
    activities: list[str]
    destination: str

    # Execution metadata
    tool_outputs: dict[str, Any]
    agent_outputs: dict[str, str]
    current_step: str
    errors: dict[str, str]
    llm_calls: int
    quality_passed: bool
    quality_issues: list[str]
    revision_count: int
    revision_hints: str
    lesson_context: str
    lessons_loaded: list[dict[str, Any]]
    review_summary: dict[str, Any]

    # Memory
    memory_context: str
    user_preferences: dict[str, Any]
    user_id: str
    thread_id: str
