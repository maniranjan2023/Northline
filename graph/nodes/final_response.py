"""Final response agent — combines all agent outputs into the itinerary."""

from __future__ import annotations

import asyncio

from langchain_core.messages import HumanMessage, SystemMessage


def final_response_agent(state: dict, llm) -> dict:
    memory_context = state.get("memory_context", "No prior user information stored yet.")

    prompt = f"""
Create a complete, personalized travel itinerary.

{memory_context}

User Query:
{state['user_query']}

Planner Brief:
{state.get('planner_output', '')}

Research:
{state.get('research_output', '')}

Flight Results:
{state.get('flight_results', '')}

Hotel Results:
{state.get('hotel_results', '')}

Activities & Weather:
{state.get('activity_results', '')}

Write a day-by-day itinerary in markdown. Personalize using stored user preferences.
Include: overview, daily plan, food tips (respect dietary preferences), transport, and budget notes.
"""

    response = asyncio.run(llm.ainvoke([
        SystemMessage(content="You are an expert travel planner creating final itineraries."),
        HumanMessage(content=prompt),
    ]))

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "current_step": "final_response_agent",
    }
