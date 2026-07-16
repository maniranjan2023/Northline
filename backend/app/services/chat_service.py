"""Chat and graph orchestration services."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

from chat_router import (
    MessageIntent,
    build_clarify_reply,
    build_greeting_reply,
    build_no_plan_reply,
    build_no_preference_reply,
    build_preference_ack,
    build_preference_updated,
    build_welcome_message,
    classify_message,
    is_explicit_correction,
)
from memory.preference_parser import (
    answer_food_preference,
    answer_what_food,
    parse_preference,
)
from memory.profile_store import upsert_and_describe
from guardrails.flags import guardrails_enabled
from main import (
    answer_follow_up,
    build_human_summary,
    build_input_state,
    build_run_config,
    extract_destination,
    load_user_plan,
    state_to_plan_dict,
    user_has_stored_plan,
)

logger = logging.getLogger(__name__)

AGENTS = [
    {"id": "planner_agent", "icon": "🧭", "title": "Planner Agent", "field": "planner_output"},
    {"id": "research_agent", "icon": "🔍", "title": "Research Agent", "field": "research_output"},
    {"id": "hotel_agent", "icon": "🏨", "title": "Hotel Agent", "field": "hotel_results"},
    {"id": "flight_agent", "icon": "✈️", "title": "Flight Agent", "field": "flight_results"},
    {"id": "activity_agent", "icon": "🎯", "title": "Activity Agent", "field": "activity_results"},
    {"id": "final_response_agent", "icon": "🗓️", "title": "Itinerary Agent", "field": "itinerary"},
]


def create_session(username: str, memory_manager) -> dict[str, Any]:
    """Create a session quickly — plan restore is handled separately via GET /plan."""
    safe_user = memory_manager.sanitize_user_id(username)
    thread_id = memory_manager.build_thread_id(safe_user)
    return {
        "username": safe_user,
        "thread_id": thread_id,
        "has_plan": False,
        "welcome_message": build_welcome_message(safe_user),
    }


def get_plan(username: str, thread_id: str, travel_graph, memory_manager) -> dict | None:
    safe_user = memory_manager.sanitize_user_id(username)
    return load_user_plan(safe_user, thread_id)


async def handle_chat_message(
    *,
    username: str,
    thread_id: str,
    message: str,
    travel_graph,
    memory_manager,
    lesson_book,
    run_id: UUID | None = None,
) -> dict[str, Any]:
    safe_user = memory_manager.sanitize_user_id(username)
    run_id = run_id or uuid4()
    text = message.strip()
    if not text:
        return {
            "intent": "clarify",
            "message": build_clarify_reply(safe_user),
            "message_type": "clarify",
            "run_id": str(run_id),
        }

    if guardrails_enabled():
        from guardrails.pipeline import check_input

        guard = check_input(text)
        if guard.blocked:
            return {
                "intent": "blocked",
                "message": guard.response,
                "message_type": "blocked",
                "guardrail_reason": guard.intent,
                "run_id": str(run_id),
            }

    has_plan = await asyncio.to_thread(user_has_stored_plan, safe_user, thread_id)
    intent = classify_message(text, has_plan)

    if intent == MessageIntent.GREETING:
        reply = build_greeting_reply(safe_user)
        return {"intent": "greeting", "message": reply, "message_type": "text", "run_id": str(run_id)}

    if intent in (MessageIntent.PREFERENCE_STATEMENT, MessageIntent.PREFERENCE_CORRECTION):
        parsed = parse_preference(text)
        memory_update = None
        if parsed:
            memory_update = await asyncio.to_thread(
                upsert_and_describe,
                safe_user,
                parsed.attribute_key,
                parsed.attribute_value,
            )
            if intent == MessageIntent.PREFERENCE_CORRECTION:
                reply = build_preference_updated(safe_user, parsed.attribute_value)
            else:
                reply = build_preference_ack(safe_user, parsed.attribute_value)
        else:
            reply = (
                f"I heard a preference update, **{safe_user}**, but couldn't tell which one. "
                "Try: *\"I like vegetarian\"* or *\"Please correct, I like non-vegetarian\"*."
            )
        response = {
            "intent": intent.value,
            "message": reply,
            "message_type": "text",
            "run_id": str(run_id),
            "user_query": text,
        }
        if memory_update:
            response["memory_update"] = memory_update
        return response

    if intent == MessageIntent.PREFERENCE_QUERY:
        from memory.profile_store import get_profile

        profile = await asyncio.to_thread(get_profile, safe_user)
        reply = answer_what_food(profile) or answer_food_preference(profile)
        if not reply:
            reply = build_no_preference_reply(safe_user)
        return {
            "intent": "preference_query",
            "message": reply,
            "message_type": "text",
            "run_id": str(run_id),
            "user_query": text,
        }

    if intent == MessageIntent.CLARIFY:
        return {
            "intent": "clarify",
            "message": build_clarify_reply(safe_user),
            "message_type": "clarify",
            "run_id": str(run_id),
        }

    if intent == MessageIntent.FOLLOW_UP:
        if not has_plan:
            return {
                "intent": "follow_up",
                "message": build_no_plan_reply(safe_user),
                "message_type": "text",
                "run_id": str(run_id),
            }
        memory_update = None
        if is_explicit_correction(text):
            parsed = parse_preference(text)
            if parsed:
                memory_update = await asyncio.to_thread(
                    upsert_and_describe,
                    safe_user,
                    parsed.attribute_key,
                    parsed.attribute_value,
                )
            else:
                await memory_manager.save_explicit_correction(safe_user, text)
        last_plan = await asyncio.to_thread(load_user_plan, safe_user, thread_id)
        reply = await asyncio.to_thread(
            answer_follow_up,
            text,
            safe_user,
            [],
            last_plan,
            thread_id,
            run_id,
        )
        if guardrails_enabled():
            from guardrails.pipeline import check_output

            out = check_output(text, reply)
            reply = out.response
        return {
            "intent": "follow_up",
            "message": reply,
            "message_type": "follow_up",
            "run_id": str(run_id),
            "user_query": text,
            **({"memory_update": memory_update} if memory_update else {}),
        }

    return {
        "intent": "new_plan",
        "message": "",
        "message_type": "plan",
        "run_id": str(run_id),
        "user_query": text,
        "stream": True,
    }


async def stream_travel_graph(
    *,
    user_query: str,
    username: str,
    thread_id: str,
    run_id: UUID,
    travel_graph,
) -> AsyncIterator[str]:
    """SSE stream of agent pipeline updates."""
    config = build_run_config(
        user_id=username,
        session_id=thread_id,
        run_name="travel_planning",
        tags=["react", "trip-planning"],
        run_id=run_id,
    )
    input_state = build_input_state(user_query=user_query, user_id=username, session_id=thread_id)

    collected: dict[str, Any] = {agent["field"]: "" for agent in AGENTS}
    collected["llm_calls"] = 0
    collected["user_query"] = user_query
    collected["langsmith_run_id"] = str(run_id)
    try:
        collected["destination"] = extract_destination(user_query)
    except Exception:
        collected["destination"] = ""

    agent_states = {agent["id"]: "pending" for agent in AGENTS}

    yield _sse(
        "pipeline",
        {
            "agent_states": agent_states,
            "agents": AGENTS,
            "status_message": "Preparing your trip…",
        },
    )

    chunk_queue: queue.Queue[tuple[str, Any]] = queue.Queue()

    def run_graph() -> None:
        try:
            for chunk in travel_graph.stream(input_state, config=config, stream_mode="updates"):
                chunk_queue.put(("chunk", chunk))
        except Exception as exc:
            logger.exception("Travel graph stream failed")
            chunk_queue.put(("error", exc))
        finally:
            chunk_queue.put(("done", None))

    threading.Thread(target=run_graph, daemon=True).start()

    while True:
        kind, payload = await asyncio.to_thread(chunk_queue.get)
        if kind == "done":
            break
        if kind == "error":
            yield _sse("error", {"message": str(payload)})
            return

        for event in _graph_chunk_events(dict(payload), collected=collected, agent_states=agent_states):
            yield event
            await asyncio.sleep(0)

    try:
        summary = build_human_summary(collected, user_query)
        if guardrails_enabled():
            from guardrails.pipeline import check_output

            out = check_output(user_query, summary)
            summary = out.response
    except Exception as exc:
        logger.exception("Failed to build trip summary")
        yield _sse("error", {"message": f"Failed to finalize trip plan: {exc}"})
        return

    yield _sse(
        "complete",
        {
            "message": summary,
            "agents": collected,
            "run_id": str(run_id),
            "user_query": user_query,
        },
    )


def _graph_chunk_events(
    chunk: dict[str, Any],
    *,
    collected: dict[str, Any],
    agent_states: dict[str, str],
) -> list[str]:
    events: list[str] = []

    for node_name, state_update in chunk.items():
        if node_name == "retrieve_memory":
            events.append(_sse("status", {"message": "Loading your travel memories…"}))
            continue

        if node_name == "store_memory":
            continue

        if node_name == "retrieve_lessons":
            for key in ("lessons_loaded", "lesson_context"):
                if key in state_update:
                    collected[key] = state_update[key]
            events.append(_sse("lessons_loaded", {"lessons_loaded": collected.get("lessons_loaded", [])}))
            if AGENTS and agent_states.get(AGENTS[0]["id"]) == "pending":
                agent_states[AGENTS[0]["id"]] = "running"
            events.append(
                _sse(
                    "pipeline",
                    {
                        "agent_states": agent_states,
                        "agents": AGENTS,
                        "status_message": f"Running {AGENTS[0]['title']}…",
                    },
                )
            )
            continue

        if node_name == "quality_check":
            for key in ("quality_passed", "quality_issues", "revision_count", "review_summary"):
                if key in state_update:
                    collected[key] = state_update[key]
            events.append(_sse("review", {"review_summary": collected.get("review_summary", {})}))
            continue

        agent_meta = next((a for a in AGENTS if a["id"] == node_name), None)
        if not agent_meta:
            continue

        collected[agent_meta["field"]] = state_update.get(
            agent_meta["field"], collected[agent_meta["field"]]
        )
        collected["llm_calls"] = state_update.get("llm_calls", collected["llm_calls"])
        if state_update.get("destination"):
            collected["destination"] = state_update["destination"]

        agent_states[node_name] = "done"
        next_agent = None
        for index, item in enumerate(AGENTS):
            if item["id"] == node_name and index + 1 < len(AGENTS):
                agent_states[AGENTS[index + 1]["id"]] = "running"
                next_agent = AGENTS[index + 1]
                break

        status_message = f"Running {next_agent['title']}…" if next_agent else "Finalizing your itinerary…"
        events.append(
            _sse(
                "pipeline",
                {
                    "agent_states": agent_states,
                    "agents": AGENTS,
                    "status_message": status_message,
                },
            )
        )
        events.append(
            _sse(
                "agent_done",
                {
                    "agent_id": node_name,
                    "agent_states": agent_states,
                    "field": agent_meta["field"],
                    "value": collected[agent_meta["field"]],
                    "destination": collected.get("destination", ""),
                },
            )
        )

    return events


def _sse(event_type: str, data: dict[str, Any]) -> str:
    payload = json.dumps({"type": event_type, "data": data}, default=str)
    return f"data: {payload}\n\n"
