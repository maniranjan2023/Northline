"""Planner agent — creates trip plan outline using user preferences."""

from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from mcp_client import extract_destination


def planner_agent(state: dict, llm) -> dict:
    memory_context = state.get("memory_context", "No prior user information stored yet.")
    user_query = state["user_query"]

    destination = ""
    try:
        destination = extract_destination(user_query)
    except Exception:
        destination = ""

    prompt = f"""
You are the lead travel planner for Voyager AI.

{memory_context}

User trip request:
{user_query}

Destination hint: {destination or "infer from request"}

Create a concise planning brief (markdown, max 200 words):
1. Trip goal and vibe
2. Suggested duration and best season
3. Must-do themes based on user preferences above
4. Flight/hotel/activity priorities for downstream agents
5. Budget considerations if known from memory

Use the user's stored preferences naturally. Do not invent preferences not in memory.
"""

    response = asyncio.run(llm.ainvoke([
        SystemMessage(content="You are an expert travel planner who personalizes trips."),
        HumanMessage(content=prompt),
    ]))

    return {
        "planner_output": response.content.strip(),
        "destination": destination,
        "messages": [AIMessage(content="Trip plan outline created")],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "current_step": "planner_agent",
    }
