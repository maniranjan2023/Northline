"""Activity agent — weather + activities for the destination."""

from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent_formatting import format_weather_markdown
from mcp_client import extract_destination, forecast_mcp_search, tavily_mcp_search, weather_mcp_search


def activity_agent(state: dict, llm) -> dict:
    memory_context = state.get("memory_context", "")
    user_query = state["user_query"]
    destination = state.get("destination") or extract_destination(user_query)

    weather_data = asyncio.run(weather_mcp_search(destination))
    forecast_data = asyncio.run(forecast_mcp_search(destination))
    weather_md = format_weather_markdown(weather_data, forecast_data)

    activities_raw = asyncio.run(
        tavily_mcp_search(f"Top activities and things to do in {destination} for travelers")
    )

    prompt = f"""
You are an activities and experiences specialist.

{memory_context}

User request: {user_query}
Research summary: {state.get("research_output", "")[:1200]}

Weather:
{weather_md}

Activity search data:
{str(activities_raw)[:2500]}

Create an activity guide (markdown, max 200 words):
1. Weather-aware packing/activity tip (1-2 lines)
2. 5 recommended activities aligned with user preferences
3. One family/couple/solo tip if relevant from memory

Include the weather section at the top.
"""

    response = asyncio.run(llm.ainvoke([
        SystemMessage(content="You plan activities and experiences for travelers."),
        HumanMessage(content=prompt),
    ]))

    return {
        "activity_results": response.content.strip(),
        "activities": [destination],
        "messages": [AIMessage(content="Activities and weather information fetched")],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "tool_outputs": {
            "activity_agent": {
                "city": destination,
                "weather": weather_data,
                "forecast": forecast_data,
                "activities": activities_raw,
            }
        },
        "current_step": "activity_agent",
    }
