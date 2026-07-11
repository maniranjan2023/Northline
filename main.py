
# LangGraph Multi-Agent Travel Booking System with Memory

import os
from typing import Annotated, Any, TypedDict
import operator
import asyncio

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from dotenv import load_dotenv

from mcp_client import (
    tavily_mcp_search,
    aviation_mcp_call,
    extract_destination,
    forecast_mcp_search,
    weather_mcp_search,
)
from db_config import create_checkpointer
from memory.memory_manager import MemoryManager
from memory.nodes.memory_load_node import memory_load_node
from memory.nodes.memory_save_node import memory_save_node
from memory.nodes.agent_wrapper import with_memory

load_dotenv(override=True)

# Shared LLM used by all agents and memory summarization.
llm = ChatGroq(model="llama-3.3-70b-versatile")

# Shared DB pool + checkpointer (short-term memory).
checkpointer, db_pool = create_checkpointer()

# Single memory entry point for the whole app.
memory_manager = MemoryManager(llm=llm, db_pool=db_pool)


class TravelState(TypedDict):
    """
    Graph state for one travel planning run.

    Short-term memory fields are saved per thread_id by PostgresSaver.
    Long-term memory context is loaded at the start of each run.
    """

    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    weather_results: str
    itinerary: str
    llm_calls: int

    # Memory fields
    user_id: str
    session_id: str
    current_task: str
    memory_context: str
    execution_status: str
    agent_outputs: dict[str, str]
    tool_outputs: dict[str, Any]
    errors: dict[str, str]
    retry_count: dict[str, int]


FLIGHT_AGENT_PROMPT = """
You are a travel flight expert.

User memory context:
{memory_context}

User Query:
{query}

Airport Information:
{airport_data}

Airline Information:
{airline_data}

Generate:
1. Likely departure airport
2. Likely arrival airport
3. Airlines serving this route
4. Typical flight duration
5. Estimated airfare range
6. Peak season pricing warning
7. Booking advice

Return concise travel guidance.
"""


def flight_agent(state: TravelState):
    """Flight agent: uses AviationStack MCP + user memory context."""
    print("\nINSIDE FLIGHT AGENT\n")
    query = state["user_query"]
    airports = ""
    airlines = ""

    try:
        airports = asyncio.run(aviation_mcp_call("list_airports"))
        airlines = asyncio.run(aviation_mcp_call("list_airlines"))

        prompt = FLIGHT_AGENT_PROMPT.format(
            memory_context=state.get("memory_context", "No prior memory."),
            query=query,
            airport_data=str(airports)[:3000],
            airline_data=str(airlines)[:3000],
        )

        response = llm.invoke([
            SystemMessage(content="You are an expert travel flight planner."),
            HumanMessage(content=prompt),
        ])
        flight_data = response.content
    except Exception as exc:
        flight_data = f"Flight information unavailable: {str(exc)}"

    return {
        "flight_results": flight_data,
        "messages": [AIMessage(content="Flight recommendations generated")],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "tool_outputs": {"flight_agent": {"airports": str(airports)[:500], "airlines": str(airlines)[:500]}},
    }


def hotel_agent(state: TravelState):
    """Hotel agent: uses Tavily MCP search + LLM summary for readable output."""
    query = f"Best hotels for {state['user_query']}"
    raw_results = asyncio.run(tavily_mcp_search(query))

    prompt = f"""
You are a hotel travel expert.

User memory context:
{state.get("memory_context", "No prior memory.")}

User trip request:
{state['user_query']}

Hotel search data:
{str(raw_results)[:3500]}

Write a concise, UI-friendly hotel briefing in markdown:
1. One short overview sentence (max 20 words)
2. Exactly 3 bullet picks using this format:
   - **Name** — one-line reason (max 12 words)
3. One practical booking tip (single short line)

Rules:
- Max 120 words total
- No JSON, no URLs, no long paragraphs
- Do not invent hotel names not supported by the search data
"""

    response = llm.invoke([
        SystemMessage(content="You summarize hotel search results into short markdown."),
        HumanMessage(content=prompt),
    ])

    return {
        "hotel_results": response.content.strip(),
        "messages": [AIMessage(content="Hotel information fetched")],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "tool_outputs": {"hotel_agent": raw_results},
    }


def weather_agent(state: TravelState):
    """Weather agent: uses OpenWeather MCP tools."""
    city = extract_destination(state["user_query"])
    weather_data = asyncio.run(weather_mcp_search(city))
    forecast_data = asyncio.run(forecast_mcp_search(city))

    return {
        "weather_results": f"Current Weather:\n{weather_data}\n\nForecast:\n{forecast_data}",
        "messages": [AIMessage(content="Weather information fetched")],
        "tool_outputs": {"weather_agent": {"city": city, "weather": weather_data, "forecast": forecast_data}},
    }


def itinerary_agent(state: TravelState):
    """Itinerary agent: combines all agent outputs + memory context."""
    prompt = f"""
Create a travel itinerary.

User memory context:
{state.get("memory_context", "No prior memory.")}

User Query:
{state['user_query']}

Flight Results:
{state['flight_results']}

Hotel Results:
{state['hotel_results']}

Weather Information:
{state['weather_results']}
"""

    response = llm.invoke([
        SystemMessage(content="You are an expert travel planner"),
        HumanMessage(content=prompt),
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def _memory_load(state: TravelState):
    """Node wrapper: load long-term memory at graph start."""
    return memory_load_node(state, memory_manager)


def _memory_save(state: TravelState):
    """Node wrapper: save long-term memory at graph end."""
    return memory_save_node(state, memory_manager)


# Build graph with only two new nodes: memory_load and memory_save.
graph = StateGraph(TravelState)

graph.add_node("memory_load", _memory_load)
graph.add_node("flight_agent", with_memory(flight_agent, "flight_agent", memory_manager))
graph.add_node("hotel_agent", with_memory(hotel_agent, "hotel_agent", memory_manager))
graph.add_node("weather_agent", with_memory(weather_agent, "weather_agent", memory_manager))
graph.add_node("itinerary_agent", with_memory(itinerary_agent, "itinerary_agent", memory_manager))
graph.add_node("memory_save", _memory_save)

graph.add_edge(START, "memory_load")
graph.add_edge("memory_load", "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "weather_agent")
graph.add_edge("weather_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "memory_save")
graph.add_edge("memory_save", END)

app = graph.compile(checkpointer=checkpointer)


def build_run_config(user_id: str, session_id: str | None = None) -> dict:
    """
    Build LangGraph config for one user session.

    user_id -> long-term memory key (username)
    session_id -> short-term memory key (thread_id)
    """
    safe_user = memory_manager._sanitize_user_id(user_id)
    thread_id = session_id or memory_manager.build_thread_id(safe_user)
    return {
        "configurable": {
            "thread_id": thread_id,
            "user_id": safe_user,
        }
    }


def build_input_state(user_query: str, user_id: str, session_id: str | None = None) -> dict:
    """
    Helper used by CLI and Streamlit.

    Creates the input state with memory context already loaded.
    """
    safe_user = memory_manager._sanitize_user_id(user_id)
    thread_id = session_id or memory_manager.build_thread_id(safe_user)
    return memory_manager.prepare_session_state(
        user_query=user_query,
        user_id=safe_user,
        session_id=thread_id,
    )


def state_to_plan_dict(state: dict[str, Any]) -> dict | None:
    """Convert graph checkpoint state into the plan dict used by the UI."""
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
        "flight_results": state.get("flight_results", ""),
        "hotel_results": state.get("hotel_results", ""),
        "weather_results": state.get("weather_results", ""),
        "itinerary": itinerary,
        "llm_calls": state.get("llm_calls", 0),
    }


def load_user_plan(user_id: str, session_id: str | None = None) -> dict | None:
    """
    Restore a user's latest trip plan.

    Order:
    1. LangGraph short-term checkpoint (thread_id)
    2. Long-term trip_plan snapshot in Neon
    """
    safe_user = memory_manager._sanitize_user_id(user_id)
    thread_id = session_id or memory_manager.build_thread_id(safe_user)
    config = build_run_config(user_id=safe_user, session_id=thread_id)

    try:
        snapshot = app.get_state(config)
        if snapshot and snapshot.values:
            plan = state_to_plan_dict(snapshot.values)
            if plan:
                return plan
    except Exception:
        pass

    return memory_manager.load_trip_plan(safe_user)


def user_has_stored_plan(user_id: str, session_id: str | None = None) -> bool:
    """True if this user has a restorable trip plan."""
    return load_user_plan(user_id, session_id) is not None


def answer_follow_up(
    user_query: str,
    username: str,
    chat_history: list[dict],
    last_plan: dict | None,
    session_id: str | None = None,
) -> str:
    """
    Answer a follow-up question using previous plan + chat history.

    This does NOT run MCP agents — only a single LLM call for speed.
    """
    safe_user = memory_manager._sanitize_user_id(username)
    if not last_plan:
        last_plan = load_user_plan(safe_user, session_id)

    history_lines = []
    for message in chat_history[-8:]:
        role = message.get("role", "user")
        content = message.get("content", "")
        history_lines.append(f"{role.upper()}: {content}")

    memory_context = memory_manager.load_memory_context(safe_user, user_query)

    plan_context = "No previous plan available."
    if last_plan:
        plan_context = f"""
Last user trip request: {last_plan.get('user_query', 'N/A')}

Destination summary: {last_plan.get('destination', 'N/A')}

Flight agent notes:
{str(last_plan.get('flight_results', ''))[:1200]}

Hotel agent notes:
{str(last_plan.get('hotel_results', ''))[:1200]}

Weather agent notes:
{str(last_plan.get('weather_results', ''))[:1200]}

Final itinerary:
{str(last_plan.get('itinerary', ''))[:2500]}
"""
    elif memory_context and "No prior memory" not in memory_context:
        plan_context = f"""
No full itinerary snapshot found, but these long-term memories exist:
{memory_context}
"""

    prompt = f"""
You are Voyager AI, a friendly travel assistant.

Answer the user's follow-up question using ONLY the previous plan and chat history below.
If the answer is not in the plan, say you do not have that detail yet and ask if they want a new plan.

Previous plan:
{plan_context}

Recent chat:
{chr(10).join(history_lines)}

User follow-up question:
{user_query}

Rules:
- Be concise, warm, and human-readable
- Do not invent destinations or prices not present in the plan
- If they ask where they planned to go, state the destination clearly
"""

    response = llm.invoke([
        SystemMessage(content="You answer follow-up travel questions from existing context only."),
        HumanMessage(content=prompt),
    ])
    return response.content.strip()


def build_human_summary(collected: dict, user_query: str) -> str:
    """
    Create a friendly summary shown before the detailed itinerary.

    Makes agent output easier to read in the chat UI.
    """
    destination = ""
    try:
        destination = extract_destination(user_query)
    except Exception:
        destination = "your destination"

    return (
        f"✅ **Your travel plan is ready!**\n\n"
        f"**Trip request:** {user_query}\n\n"
        f"**Destination:** {destination}\n\n"
        f"I checked flights, hotels, and weather with my specialist agents. "
        f"Here is your full itinerary below — expand each agent card for details."
    )


if __name__ == "__main__":
    user_id = input("Enter your username: ").strip() or "guest"
    session_id = memory_manager.build_thread_id(user_id)
    config = build_run_config(user_id=user_id, session_id=session_id)

    print(f"Using session (short-term): {session_id}")
    print(f"Using user (long-term): {memory_manager._sanitize_user_id(user_id)}")

    user_input = input("Enter travel request: ")
    result = app.invoke(
        build_input_state(user_input, user_id=user_id, session_id=session_id),
        config=config,
    )

    print("\nFINAL RESPONSE:\n")
    print(result.get("itinerary", ""))
