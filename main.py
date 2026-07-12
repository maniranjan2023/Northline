
# LangGraph Multi-Agent Travel Booking System with Memory

import asyncio
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv

from observability import configure_langsmith

load_dotenv(override=True)
configure_langsmith()

from db_config import create_checkpointer
from graph.builder import build_travel_graph
from mcp_client import extract_destination
from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

# Shared LLM used by all agents and memory extraction.
llm = ChatGroq(model="llama-3.3-70b-versatile")

# Short-term memory: PostgresSaver checkpoints per thread_id.
checkpointer, db_pool = create_checkpointer()

# Long-term memory: Mem0 (injected into nodes via MemoryManager).
memory_manager = MemoryManager(llm=llm)

# Compiled LangGraph app with checkpointer.
app = build_travel_graph(llm, memory_manager, checkpointer)


def build_run_config(
    user_id: str,
    session_id: str | None = None,
    *,
    run_name: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """
    Build LangGraph config for one user session.

    user_id  -> long-term Mem0 key
    thread_id -> short-term PostgresSaver key (session_id)
    """
    safe_user = memory_manager.sanitize_user_id(user_id)
    thread_id = session_id or memory_manager.build_thread_id(safe_user)
    trace_tags = ["voyager-ai", "langgraph", f"user:{safe_user}"]
    if tags:
        trace_tags.extend(tags)

    return {
        "configurable": {
            "thread_id": thread_id,
            "user_id": safe_user,
        },
        "metadata": {
            "user_id": safe_user,
            "thread_id": thread_id,
            "app": "voyager-ai",
        },
        "run_name": run_name or "travel_planning",
        "tags": trace_tags,
    }


def build_input_state(user_query: str, user_id: str, session_id: str | None = None) -> dict:
    """
    Create initial graph state. Long-term memory is loaded by RetrieveMemoryNode.
    """
    safe_user = memory_manager.sanitize_user_id(user_id)
    thread_id = session_id or memory_manager.build_thread_id(safe_user)
    return memory_manager.build_initial_state(
        user_query=user_query,
        user_id=safe_user,
        thread_id=thread_id,
    )


def state_to_plan_dict(state: dict[str, Any]) -> dict | None:
    """Convert checkpointed graph state into the plan dict used by the UI."""
    itinerary = state.get("itinerary", "")
    if not itinerary:
        return None

    user_query = state.get("user_query", "")
    destination = state.get("destination", "")
    if not destination and user_query:
        try:
            destination = extract_destination(user_query)
        except Exception:
            destination = ""

    return {
        "user_query": user_query,
        "destination": destination,
        "planner_output": state.get("planner_output", ""),
        "research_output": state.get("research_output", ""),
        "flight_results": state.get("flight_results", ""),
        "hotel_results": state.get("hotel_results", ""),
        "activity_results": state.get("activity_results", ""),
        "weather_results": state.get("activity_results", ""),  # UI backward compat
        "itinerary": itinerary,
        "llm_calls": state.get("llm_calls", 0),
    }


def load_user_plan(user_id: str, session_id: str | None = None) -> dict | None:
    """
    Restore a user's latest trip plan from LangGraph short-term checkpoint.

    PostgresSaver is keyed by thread_id.
    """
    safe_user = memory_manager.sanitize_user_id(user_id)
    thread_id = session_id or memory_manager.build_thread_id(safe_user)
    config = build_run_config(user_id=safe_user, session_id=thread_id)

    try:
        snapshot = app.get_state(config)
        if snapshot and snapshot.values:
            plan = state_to_plan_dict(snapshot.values)
            if plan:
                logger.info("Checkpoint restored: user_id=%s thread_id=%s", safe_user, thread_id)
                return plan
    except Exception as exc:
        logger.error("Checkpoint restoration failed: %s", exc)
        raise

    return None


def user_has_stored_plan(user_id: str, session_id: str | None = None) -> bool:
    """True if this user has a restorable trip plan in the checkpoint."""
    try:
        return load_user_plan(user_id, session_id) is not None
    except Exception:
        return False


def answer_follow_up(
    user_query: str,
    username: str,
    chat_history: list[dict],
    last_plan: dict | None,
    session_id: str | None = None,
) -> str:
    """
    Answer a follow-up using checkpoint plan + Mem0 long-term memory.

    Does NOT re-run the full agent graph.
    """
    safe_user = memory_manager.sanitize_user_id(username)
    if not last_plan:
        try:
            last_plan = load_user_plan(safe_user, session_id)
        except Exception:
            last_plan = None

    history_lines = []
    for message in chat_history[-8:]:
        role = message.get("role", "user")
        content = message.get("content", "")
        history_lines.append(f"{role.upper()}: {content}")

    memory_context = asyncio.run(memory_manager.load_memory_context(safe_user, user_query))

    plan_context = "No previous plan available."
    if last_plan:
        plan_context = f"""
Last user trip request: {last_plan.get('user_query', 'N/A')}
Destination: {last_plan.get('destination', 'N/A')}

Planner brief:
{str(last_plan.get('planner_output', ''))[:800]}

Flight notes:
{str(last_plan.get('flight_results', ''))[:1200]}

Hotel notes:
{str(last_plan.get('hotel_results', ''))[:1200]}

Activities & weather:
{str(last_plan.get('activity_results', last_plan.get('weather_results', '')))[:1200]}

Final itinerary:
{str(last_plan.get('itinerary', ''))[:2500]}
"""
    elif memory_context and "No prior" not in memory_context:
        plan_context = f"Known user information:\n{memory_context}"

    prompt = f"""
You are Voyager AI, a friendly travel assistant.

{memory_context}

Answer the follow-up using the previous plan and chat history.
If the answer is not available, say so and offer to create a new plan.

Previous plan:
{plan_context}

Recent chat:
{chr(10).join(history_lines)}

User follow-up:
{user_query}
"""

    response = llm.invoke([
        SystemMessage(content="You answer follow-up travel questions from existing context only."),
        HumanMessage(content=prompt),
    ])
    return response.content.strip()


def build_human_summary(collected: dict, user_query: str) -> str:
    """Friendly summary shown before the detailed itinerary in the UI."""
    destination = collected.get("destination", "")
    if not destination:
        try:
            destination = extract_destination(user_query)
        except Exception:
            destination = "your destination"

    return (
        f"✅ **Your travel plan is ready!**\n\n"
        f"**Trip request:** {user_query}\n\n"
        f"**Destination:** {destination}\n\n"
        f"I checked flights, hotels, activities, and weather with my specialist agents. "
        f"Here is your full itinerary below — expand each agent card for details."
    )


if __name__ == "__main__":
    user_id = input("Enter your username: ").strip() or "guest"
    session_id = memory_manager.build_thread_id(user_id)
    config = build_run_config(user_id=user_id, session_id=session_id)

    print(f"Short-term (thread_id): {session_id}")
    print(f"Long-term (user_id): {memory_manager.sanitize_user_id(user_id)}")

    user_input = input("Enter travel request: ")
    result = app.invoke(
        build_input_state(user_input, user_id=user_id, session_id=session_id),
        config=config,
    )

    print("\nFINAL RESPONSE:\n")
    print(result.get("itinerary", ""))
