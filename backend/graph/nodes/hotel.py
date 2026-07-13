"""Hotel agent — hotel search via Tavily MCP."""

from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from mcp_client import tavily_mcp_search


def hotel_agent(state: dict, llm) -> dict:
    memory_context = state.get("memory_context", "")
    user_query = state["user_query"]
    search_query = f"Best hotels for {user_query}"
    raw_results = asyncio.run(tavily_mcp_search(search_query))

    prompt = f"""
You are a hotel travel expert.

{memory_context}

User trip request: {user_query}
Planner brief: {state.get("planner_output", "")[:1200]}

Hotel search data:
{str(raw_results)[:3500]}

Write a concise hotel briefing in markdown (max 120 words):
1. One short overview sentence
2. Exactly 3 bullet picks: **Hotel Name** — one-line reason
3. Final line starting with "Tip:"

Respect user preferences from memory (luxury, budget, family, etc.).
"""

    response = asyncio.run(llm.ainvoke([
        SystemMessage(content="You summarize hotel search results into short markdown."),
        HumanMessage(content=prompt),
    ]))

    return {
        "hotel_results": response.content.strip(),
        "messages": [AIMessage(content="Hotel information fetched")],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "tool_outputs": {"hotel_agent": raw_results},
        "current_step": "hotel_agent",
    }
