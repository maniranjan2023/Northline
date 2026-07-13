"""Flight agent — route guidance via AviationStack MCP."""

from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from mcp_client import aviation_mcp_call


FLIGHT_AGENT_PROMPT = """
You are a travel flight expert.

{memory_context}

User Query:
{query}

Planner brief:
{planner_brief}

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

Respect user flight preferences from memory (direct flights, preferred airline, etc.).
Return concise travel guidance.
"""


def flight_agent(state: dict, llm) -> dict:
    query = state["user_query"]
    memory_context = state.get("memory_context", "No prior user information stored yet.")
    airports = ""
    airlines = ""

    try:
        airports = asyncio.run(aviation_mcp_call("list_airports"))
        airlines = asyncio.run(aviation_mcp_call("list_airlines"))

        prompt = FLIGHT_AGENT_PROMPT.format(
            memory_context=memory_context,
            query=query,
            planner_brief=state.get("planner_output", "")[:1200],
            airport_data=str(airports)[:3000],
            airline_data=str(airlines)[:3000],
        )

        response = asyncio.run(llm.ainvoke([
            SystemMessage(content="You are an expert travel flight planner."),
            HumanMessage(content=prompt),
        ]))
        flight_data = response.content
    except Exception as exc:
        flight_data = f"Flight information unavailable: {str(exc)}"

    return {
        "flight_results": flight_data,
        "messages": [AIMessage(content="Flight recommendations generated")],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "tool_outputs": {"flight_agent": {"airports": str(airports)[:500], "airlines": str(airlines)[:500]}},
        "current_step": "flight_agent",
    }
