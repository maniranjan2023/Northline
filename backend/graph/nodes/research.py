"""Research agent — destination research via Tavily MCP."""

from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from mcp_client import extract_destination, tavily_mcp_search


def research_agent(state: dict, llm) -> dict:
    memory_context = state.get("memory_context", "")
    user_query = state["user_query"]
    destination = state.get("destination") or extract_destination(user_query)

    search_query = f"Travel guide {destination} best areas attractions local tips 2025"
    raw_results = asyncio.run(tavily_mcp_search(search_query))

    prompt = f"""
You are a destination research specialist.

{memory_context}

User request: {user_query}
Planner brief: {state.get("planner_output", "")[:1500]}

Raw research data:
{str(raw_results)[:3500]}

Write a concise research summary (markdown, max 180 words):
- Top neighborhoods/areas
- Key attractions aligned with user preferences
- Local culture tips
- Safety/season notes if relevant
"""

    response = asyncio.run(llm.ainvoke([
        SystemMessage(content="You summarize destination research for travel planners."),
        HumanMessage(content=prompt),
    ]))

    return {
        "research_output": response.content.strip(),
        "messages": [AIMessage(content="Destination research completed")],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "tool_outputs": {"research_agent": raw_results},
        "current_step": "research_agent",
    }
