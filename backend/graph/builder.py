"""LangGraph builder — wires memory nodes and travel agents."""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.postgres import PostgresSaver

from graph.nodes.activities import activity_agent
from graph.nodes.agent_wrapper import with_memory
from graph.nodes.final_response import final_response_agent
from graph.nodes.flight import flight_agent
from graph.nodes.hotel import hotel_agent
from graph.nodes.planner import planner_agent
from graph.nodes.quality_check import quality_check_node
from graph.nodes.research import research_agent
from graph.nodes.retrieve_lessons import retrieve_lessons_node
from graph.nodes.retrieve_memory import retrieve_memory_node
from graph.nodes.store_memory import store_memory_node
from lessons.service import LessonBookService
from memory.memory_manager import MemoryManager
from memory.state import TravelState


def build_travel_graph(
    llm,
    memory_manager: MemoryManager,
    checkpointer: PostgresSaver,
    lesson_book: LessonBookService,
):
    """
    Graph flow:
    START → retrieve_memory → retrieve_lessons → planner → research → hotel → flight
          → activity → final_response → quality_check → store_memory → END
    """
    graph = StateGraph(TravelState)

    graph.add_node(
        "retrieve_memory",
        partial(retrieve_memory_node, memory_manager=memory_manager),
    )
    graph.add_node(
        "retrieve_lessons",
        partial(retrieve_lessons_node, lesson_book=lesson_book),
    )
    graph.add_node(
        "planner_agent",
        with_memory(partial(planner_agent, llm=llm), "planner_agent", memory_manager),
    )
    graph.add_node(
        "research_agent",
        with_memory(partial(research_agent, llm=llm), "research_agent", memory_manager),
    )
    graph.add_node(
        "hotel_agent",
        with_memory(partial(hotel_agent, llm=llm), "hotel_agent", memory_manager),
    )
    graph.add_node(
        "flight_agent",
        with_memory(partial(flight_agent, llm=llm), "flight_agent", memory_manager),
    )
    graph.add_node(
        "activity_agent",
        with_memory(partial(activity_agent, llm=llm), "activity_agent", memory_manager),
    )
    graph.add_node(
        "final_response_agent",
        with_memory(partial(final_response_agent, llm=llm), "final_response_agent", memory_manager),
    )
    graph.add_node(
        "store_memory",
        partial(store_memory_node, memory_manager=memory_manager),
    )
    graph.add_node(
        "quality_check",
        partial(quality_check_node, lesson_book=lesson_book),
    )

    graph.add_edge(START, "retrieve_memory")
    graph.add_edge("retrieve_memory", "retrieve_lessons")
    graph.add_edge("retrieve_lessons", "planner_agent")
    graph.add_edge("planner_agent", "research_agent")
    graph.add_edge("research_agent", "hotel_agent")
    graph.add_edge("hotel_agent", "flight_agent")
    graph.add_edge("flight_agent", "activity_agent")
    graph.add_edge("activity_agent", "final_response_agent")
    graph.add_edge("final_response_agent", "quality_check")
    graph.add_edge("quality_check", "store_memory")
    graph.add_edge("store_memory", END)

    return graph.compile(checkpointer=checkpointer)
