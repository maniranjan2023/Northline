"""
Streamlit chat UI for Voyager AI.

Features:
- Username gate before chat
- Welcome message on first open (no agents run)
- Message router: greeting / follow-up / new plan
- Follow-ups answered from previous plan without re-running agents
- Friendly agent pipeline UI with human-readable responses
"""

import os
import asyncio
import warnings
import logging

# Reduce noisy third-party logs (TensorFlow, torch, LangChain deprecations).
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
warnings.filterwarnings(
    "ignore",
    message=r".*HuggingFaceEmbeddings.*deprecated.*",
    category=DeprecationWarning,
)
warnings.filterwarnings("ignore", message=r".*torch\.classes.*")
logging.getLogger("nemoguardrails").setLevel(logging.WARNING)


class _SuppressTorchClassesLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "torch.classes" not in record.getMessage()


logging.getLogger().addFilter(_SuppressTorchClassesLog())

from observability import configure_langsmith

configure_langsmith()

import json
import re
from datetime import datetime

import streamlit as st

from agent_formatting import format_weather_markdown, parse_mcp_result, split_hotel_markdown
from chat_router import (
    MessageIntent,
    build_clarify_reply,
    build_greeting_reply,
    build_no_plan_reply,
    build_welcome_message,
    classify_message,
)
from guardrails.pipeline import check_input, check_output, guardrails_enabled
from main import (
    answer_follow_up,
    app,
    build_human_summary,
    build_input_state,
    build_run_config,
    extract_destination,
    load_user_plan,
    memory_manager,
    user_has_stored_plan,
)

st.set_page_config(
    page_title="Voyager AI — Travel Chat",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

AGENTS = [
    {
        "id": "planner_agent",
        "icon": "🧭",
        "title": "Planner Agent",
        "subtitle": "Creates your personalized trip outline",
        "field": "planner_output",
    },
    {
        "id": "research_agent",
        "icon": "🔍",
        "title": "Research Agent",
        "subtitle": "Researches destination highlights",
        "field": "research_output",
    },
    {
        "id": "hotel_agent",
        "icon": "🏨",
        "title": "Hotel Agent",
        "subtitle": "Searches hotels and stays",
        "field": "hotel_results",
    },
    {
        "id": "flight_agent",
        "icon": "✈️",
        "title": "Flight Agent",
        "subtitle": "Finds routes, airlines, and fares",
        "field": "flight_results",
    },
    {
        "id": "activity_agent",
        "icon": "🎯",
        "title": "Activity Agent",
        "subtitle": "Weather, activities, and experiences",
        "field": "activity_results",
    },
    {
        "id": "final_response_agent",
        "icon": "🗓️",
        "title": "Itinerary Agent",
        "subtitle": "Builds your day-by-day plan",
        "field": "itinerary",
    },
]

QUICK_PROMPTS = [
    "Plan a 7-day Japan trip under ₹2L",
    "5-day Paris romantic getaway",
    "Dubai weekend luxury trip",
]

STATUS_LABELS = {
    "pending": ("⏳", "Waiting"),
    "running": ("🔄", "Working now"),
    "done": ("✅", "Done"),
    "error": ("❌", "Issue"),
}


def inject_styles() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp {
    background: radial-gradient(ellipse at top, rgba(59,130,246,0.14), transparent), #06080f;
}
.block-container { max-width: 920px; padding-top: 1.2rem; }
.hero-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(148,163,184,0.16);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    margin-bottom: 1rem;
}
.agent-pill {
    text-align: center;
    padding: 0.7rem 0.45rem;
    border-radius: 14px;
    border: 1px solid rgba(148,163,184,0.16);
    background: rgba(255,255,255,0.02);
    min-height: 92px;
}
.agent-pill.running {
    border-color: rgba(59,130,246,0.55);
    background: rgba(59,130,246,0.12);
    box-shadow: 0 0 0 1px rgba(59,130,246,0.2);
}
.agent-pill.done {
    border-color: rgba(16,185,129,0.5);
    background: rgba(16,185,129,0.1);
}
.agent-pill.error {
    border-color: rgba(239,68,68,0.45);
    background: rgba(239,68,68,0.08);
}
.follow-up-badge {
    display: inline-block;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    background: rgba(167,139,250,0.15);
    border: 1px solid rgba(167,139,250,0.35);
    color: #d8c4ff;
    font-size: 0.72rem;
    font-weight: 600;
}
[data-testid="stChatMessage"] {
    border: 1px solid rgba(148,163,184,0.14);
    border-radius: 14px;
    background: rgba(255,255,255,0.02);
    margin-bottom: 0.6rem;
}
[data-testid="stStatusWidget"] {
    border-radius: 14px !important;
    border: 1px solid rgba(148,163,184,0.14) !important;
    margin-bottom: 0.5rem;
}
.hotel-pick-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(148,163,184,0.14);
    border-radius: 12px;
    padding: 0.65rem 0.75rem;
    margin-bottom: 0.45rem;
}
.hotel-pick-title {
    font-weight: 600;
    color: #edf4ff;
    font-size: 0.88rem;
}
.hotel-pick-snippet {
    color: #9fb2cc;
    font-size: 0.78rem;
    margin-top: 0.2rem;
    line-height: 1.35;
}
.weather-now-card {
    background: rgba(59,130,246,0.12);
    border: 1px solid rgba(59,130,246,0.28);
    border-radius: 12px;
    padding: 0.75rem 0.9rem;
    margin-bottom: 0.55rem;
}
.weather-forecast-row {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.45rem 0;
    border-bottom: 1px solid rgba(148,163,184,0.12);
    font-size: 0.82rem;
    color: #d7e6ff;
}
.weather-forecast-row:last-child { border-bottom: none; }
.thinking-bubble {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.65rem 0.9rem;
    border-radius: 12px;
    background: rgba(59,130,246,0.1);
    border: 1px solid rgba(59,130,246,0.28);
    color: #b9d4ff;
    font-size: 0.88rem;
    margin-bottom: 0.35rem;
}
.thinking-dots span {
    display: inline-block;
    width: 6px;
    height: 6px;
    margin: 0 2px;
    border-radius: 50%;
    background: #60a5fa;
    animation: thinking-bounce 1.2s infinite ease-in-out;
}
.thinking-dots span:nth-child(2) { animation-delay: 0.15s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.3s; }
@keyframes thinking-bounce {
    0%, 80%, 100% { transform: translateY(0); opacity: 0.45; }
    40% { transform: translateY(-5px); opacity: 1; }
}
.running-status {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.8rem 1rem;
    border-radius: 14px;
    background: linear-gradient(90deg, rgba(59,130,246,0.16), rgba(16,185,129,0.08));
    border: 1px solid rgba(59,130,246,0.35);
    color: #dbeafe;
    font-size: 0.9rem;
    margin: 0.25rem 0 0.75rem 0;
    animation: running-pulse 1.8s ease-in-out infinite;
}
@keyframes running-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.15); }
    50% { box-shadow: 0 0 0 6px rgba(59,130,246,0.05); }
}
        """,
        unsafe_allow_html=True,
    )


def init_session_state() -> None:
    defaults = {
        "username_input": "",
        "saved_username": "",
        "chat_started": False,
        "thread_id": "",
        "chat_messages": [],
        "last_plan": None,
        "welcome_shown": False,
        "last_download": None,
        "pending_query": None,
        "processing_phase": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def save_username(raw_username: str) -> None:
    username = memory_manager.sanitize_user_id(raw_username)
    if not username or username == "anonymous":
        st.warning("Please enter a valid username.")
        return

    switching_user = (
        st.session_state.saved_username
        and st.session_state.saved_username != username
    )
    if switching_user:
        st.session_state.chat_messages = []
        st.session_state.welcome_shown = False

    thread_id = memory_manager.build_thread_id(username)
    st.session_state.saved_username = username
    st.session_state.thread_id = thread_id
    st.session_state.chat_started = True
    st.session_state.username_input = raw_username.strip()

    # Restore this user's saved plan from DB (short-term checkpoint or long-term snapshot).
    st.session_state.last_plan = load_user_plan(username, thread_id)


def _loads_if_json(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _clean_snippet(text: str, limit: int = 110) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def _extract_hotel_picks(value) -> tuple[str, list[dict]]:
    """Parse Tavily/raw hotel payloads into a short summary + top picks."""
    summary = ""
    picks: list[dict] = []
    seen_titles: set[str] = set()

    def add_pick(title: str, snippet: str = "", url: str = "") -> None:
        title = (title or "Hotel option").strip()
        key = title.lower()
        if not title or key in seen_titles:
            return
        seen_titles.add(key)
        picks.append({
            "title": title,
            "snippet": _clean_snippet(snippet),
            "url": (url or "").strip(),
        })

    def consume_results(results: list) -> None:
        for result in results[:4]:
            if not isinstance(result, dict):
                continue
            add_pick(
                result.get("title", ""),
                result.get("content") or result.get("snippet") or "",
                result.get("url", ""),
            )

    payload = value
    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            payload = _loads_if_json(stripped) or payload
        elif not picks and len(stripped) < 280 and "\n" not in stripped:
            summary = stripped

    if isinstance(payload, dict):
        if payload.get("summary"):
            summary = str(payload["summary"])[:220]
        if payload.get("picks"):
            for item in payload["picks"][:4]:
                if isinstance(item, dict):
                    add_pick(item.get("title", ""), item.get("snippet", ""), item.get("url", ""))
        if payload.get("answer"):
            summary = summary or _clean_snippet(str(payload["answer"]), 180)
        consume_results(payload.get("results", []))
    elif isinstance(payload, list):
        for block in payload:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                inner = _loads_if_json(block.get("text", ""))
                if isinstance(inner, dict):
                    if inner.get("answer"):
                        summary = summary or _clean_snippet(str(inner["answer"]), 180)
                    consume_results(inner.get("results", []))
                elif isinstance(inner, list):
                    consume_results(inner)
            elif block.get("title"):
                add_pick(block.get("title", ""), block.get("content", ""), block.get("url", ""))

    return summary, picks[:3]


def render_hotel_agent_ui(value) -> None:
    """Compact hotel UI — overview, pick cards, and booking tip."""
    text = str(value or "").strip()
    summary, picks = _extract_hotel_picks(value)

    # Prefer structured markdown from hotel_agent LLM summary.
    if text and not text.startswith("[{") and ("**" in text or text.startswith("-")):
        overview, markdown_picks, tip = split_hotel_markdown(text)
        if overview:
            st.info(overview)
        if markdown_picks:
            st.caption(f"Top {len(markdown_picks)} stay option{'s' if len(markdown_picks) != 1 else ''}")
            for index, pick in enumerate(markdown_picks, start=1):
                with st.container(border=True):
                    st.markdown(pick if pick.startswith("**") else f"**{index}.** {pick}")
            if tip:
                st.caption(f"💡 **Tip:** {tip}")
            return
        if not picks and len(text) < 900:
            st.markdown(text)
            return

    if summary:
        st.info(summary)

    if picks:
        st.caption(f"Top {len(picks)} stay option{'s' if len(picks) != 1 else ''}")
        for index, pick in enumerate(picks, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {pick['title']}**")
                st.caption(pick["snippet"] or "Recommended stay for your trip.")
                if pick["url"]:
                    st.markdown(f"[View source]({pick['url']})")
        return

    st.caption("Hotel suggestions")
    st.markdown(_clean_snippet(text, 280) or "_No hotel details available._")


def render_weather_agent_ui(value) -> None:
    """Readable weather cards from formatted markdown or raw MCP payload."""
    text = str(value or "").strip()

    # Already formatted markdown from weather_agent.
    if text.startswith("###") or "**Right now:**" in text:
        st.markdown(text)
        return

    # Legacy raw MCP dump — parse and reformat.
    if "Current Weather:" in text and "Forecast:" in text:
        parts = text.split("Forecast:", 1)
        weather_part = parts[0].replace("Current Weather:", "").strip()
        forecast_part = parts[1].strip() if len(parts) > 1 else ""
        text = format_weather_markdown(weather_part, forecast_part)
        st.markdown(text)
        return

    parsed = parse_mcp_result(value)
    if isinstance(parsed, dict):
        st.markdown(format_weather_markdown(parsed, parsed))
        return

    st.markdown(_clean_snippet(text, 500) or "_No weather details available._")


def format_agent_output(agent_id: str, value) -> str:
    """Turn raw MCP/LLM output into clean readable markdown."""
    if not value:
        return "_No details available yet._"

    if agent_id == "hotel_agent":
        text = str(value).strip()
        if len(text) < 900 and not text.startswith("[{"):
            return text
        summary, picks = _extract_hotel_picks(value)
        if picks:
            lines = [summary] if summary else ["**Top hotel picks:**"]
            for index, pick in enumerate(picks, start=1):
                lines.append(f"{index}. **{pick['title']}** — {pick['snippet']}")
            return "\n".join(lines)
        return _clean_snippet(text, 280)

    if agent_id in {"weather_agent", "activity_agent"}:
        text = str(value).strip()
        if text.startswith("###") or "**Right now:**" in text:
            return text
        if "Current Weather:" in text and "Forecast:" in text:
            parts = text.split("Forecast:", 1)
            weather_part = parts[0].replace("Current Weather:", "").strip()
            forecast_part = parts[1].strip() if len(parts) > 1 else ""
            return format_weather_markdown(weather_part, forecast_part)
        parsed = parse_mcp_result(value)
        if isinstance(parsed, dict):
            return format_weather_markdown(parsed, parsed)
        return _clean_snippet(text, 500)

    text = str(value).strip()
    return re.sub(r"\n{3,}", "\n\n", text)[:2200]


def render_agent_pipeline(agent_states: dict[str, str]) -> None:
    """Show which agent is active in a friendly pill layout."""
    cols = st.columns(len(AGENTS))
    for col, agent in zip(cols, AGENTS):
        state = agent_states.get(agent["id"], "pending")
        css = state if state in {"running", "done", "error"} else ""
        icon, label = STATUS_LABELS.get(state, ("⏳", state))
        with col:
            st.markdown(
                f"""
<div class="agent-pill {css}">
  <div style="font-size:1.25rem;">{agent['icon']}</div>
  <div style="font-weight:600; font-size:0.78rem; color:#edf4ff; margin-top:0.25rem;">
    {agent['title']}
  </div>
  <div style="font-size:0.66rem; color:#93a8c3; margin-top:0.15rem;">
    {icon} {label}
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )


def render_agent_card_content(agent_id: str, value) -> None:
    """Render one agent result with agent-specific friendly formatting."""
    if agent_id == "hotel_agent":
        render_hotel_agent_ui(value)
    elif agent_id in {"activity_agent", "weather_agent"}:
        render_weather_agent_ui(value)
    else:
        st.markdown(format_agent_output(agent_id, value))


def render_agent_cards(collected: dict, expanded_agent: str | None = None) -> None:
    """Show each agent response in a status card."""
    for agent in AGENTS:
        value = collected.get(agent["field"], "")
        if not value:
            continue
        label = f"{agent['icon']} {agent['title']} — {agent['subtitle']}"
        with st.status(label, state="complete", expanded=(agent["id"] == expanded_agent)):
            render_agent_card_content(agent["id"], value)


def run_travel_graph(
    user_query: str,
    username: str,
    thread_id: str,
    thinking_slot=None,
) -> dict:
    """Run full agent pipeline for a NEW trip planning request."""
    if thinking_slot is not None:
        thinking_slot.empty()

    config = build_run_config(
        user_id=username,
        session_id=thread_id,
        run_name="travel_planning",
        tags=["streamlit", "trip-planning"],
    )
    input_state = build_input_state(
        user_query=user_query,
        user_id=username,
        session_id=thread_id,
    )

    collected = {agent["field"]: "" for agent in AGENTS}
    collected["llm_calls"] = 0
    collected["user_query"] = user_query

    try:
        collected["destination"] = extract_destination(user_query)
    except Exception:
        collected["destination"] = ""

    agent_states = {agent["id"]: "pending" for agent in AGENTS}
    if AGENTS:
        agent_states[AGENTS[0]["id"]] = "running"

    pipeline_slot = st.empty()

    with pipeline_slot.container():
        st.markdown("#### 🤖 Agents at work")
        st.caption("I'm calling each specialist agent one by one for your trip.")
        render_agent_pipeline(agent_states)

    for chunk in app.stream(input_state, config=config, stream_mode="updates"):
        for node_name, state_update in chunk.items():
            if node_name in {"retrieve_memory", "store_memory"}:
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

            for index, item in enumerate(AGENTS):
                if item["id"] == node_name and index + 1 < len(AGENTS):
                    agent_states[AGENTS[index + 1]["id"]] = "running"
                    break

            with pipeline_slot.container():
                st.markdown("#### 🤖 Agents at work")
                st.caption(f"Finished **{agent_meta['title']}** — moving to the next agent.")
                render_agent_pipeline(agent_states)

    return collected


def show_welcome_if_needed() -> None:
    """Show one-time welcome message when chat opens."""
    if st.session_state.welcome_shown:
        return

    welcome = build_welcome_message(st.session_state.saved_username)
    st.session_state.chat_messages.append(
        {
            "role": "assistant",
            "content": welcome,
            "message_type": "welcome",
        }
    )
    st.session_state.welcome_shown = True


def append_assistant_message(content: str, message_type: str = "text", agents: dict | None = None):
    st.session_state.chat_messages.append(
        {
            "role": "assistant",
            "content": content,
            "message_type": message_type,
            "agents": agents,
        }
    )


def render_thinking_indicator(label: str) -> None:
    """Animated running indicator shown while a reply is generated."""
    st.markdown(
        f"""
<div class="running-status">
  <span class="thinking-dots"><span></span><span></span><span></span></span>
  <span><strong>Running</strong> — {label}</span>
</div>
        """,
        unsafe_allow_html=True,
    )


def process_pending_query(user_query: str, thinking_slot=None) -> dict:
    """
    Run guardrails, routing, and response generation for one user message.

    Returns a dict with keys: content, message_type, agents (optional).
    """
    input_guard = check_input(user_query)
    if input_guard.blocked:
        return {
            "content": input_guard.response,
            "message_type": "guardrail_blocked",
            "agents": None,
        }

    if not st.session_state.last_plan:
        st.session_state.last_plan = load_user_plan(
            st.session_state.saved_username,
            st.session_state.thread_id,
        )

    has_plan = (
        st.session_state.last_plan is not None
        or user_has_stored_plan(
            st.session_state.saved_username,
            st.session_state.thread_id,
        )
    )
    intent = classify_message(user_query, has_previous_plan=has_plan)

    if intent == MessageIntent.GREETING:
        reply = guard_assistant_reply(
            user_query,
            build_greeting_reply(st.session_state.saved_username),
        )
        return {"content": reply, "message_type": "greeting", "agents": None}

    if intent == MessageIntent.FOLLOW_UP:
        if not st.session_state.last_plan:
            st.session_state.last_plan = load_user_plan(
                st.session_state.saved_username,
                st.session_state.thread_id,
            )

        if not st.session_state.last_plan:
            reply = guard_assistant_reply(
                user_query,
                build_no_plan_reply(st.session_state.saved_username),
            )
            return {"content": reply, "message_type": "no_plan", "agents": None}

        reply = guard_assistant_reply(
            user_query,
            answer_follow_up(
                user_query=user_query,
                username=st.session_state.saved_username,
                chat_history=st.session_state.chat_messages,
                last_plan=st.session_state.last_plan,
                session_id=st.session_state.thread_id,
            ),
        )
        return {"content": reply, "message_type": "follow_up", "agents": None}

    if intent == MessageIntent.CLARIFY:
        reply = guard_assistant_reply(
            user_query,
            build_clarify_reply(st.session_state.saved_username),
        )
        return {"content": reply, "message_type": "clarify", "agents": None}

    collected = run_travel_graph(
        user_query=user_query,
        username=st.session_state.saved_username,
        thread_id=st.session_state.thread_id,
        thinking_slot=thinking_slot,
    )

    summary = build_human_summary(collected, user_query)
    itinerary = collected.get("itinerary", "I could not build an itinerary.")
    full_reply = f"{summary}\n\n---\n\n### 🗓️ Your itinerary\n\n{itinerary}"
    full_reply = guard_assistant_reply(user_query, full_reply)

    st.session_state.last_plan = collected

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"travel_plan_{st.session_state.saved_username}_{timestamp}.md"
    save_dir = os.path.join(os.path.dirname(__file__), "travel_plans")
    os.makedirs(save_dir, exist_ok=True)
    file_content = (
        f"# Travel Plan\n\n"
        f"**User:** {st.session_state.saved_username}\n\n"
        f"**Query:** {user_query}\n\n"
        f"## Itinerary\n{itinerary}\n"
    )
    with open(os.path.join(save_dir, filename), "w", encoding="utf-8") as file:
        file.write(file_content)
    st.session_state.last_download = {
        "filename": filename,
        "content": file_content,
    }

    return {"content": full_reply, "message_type": "plan", "agents": collected}


def thinking_label_for_query(user_query: str) -> str:
    """Pick a user-friendly thinking message before routing completes."""
    preview = classify_message(
        user_query,
        has_previous_plan=bool(
            st.session_state.last_plan
            or user_has_stored_plan(
                st.session_state.saved_username,
                st.session_state.thread_id,
            )
        ),
    )
    labels = {
        MessageIntent.GREETING: "Voyager AI is preparing a welcome reply…",
        MessageIntent.FOLLOW_UP: "Voyager AI is recalling your trip and thinking…",
        MessageIntent.CLARIFY: "Voyager AI is thinking about how to help…",
        MessageIntent.NEW_PLAN: "Voyager AI is coordinating specialist agents…",
    }
    return labels.get(preview, "Voyager AI is thinking…")


def guard_assistant_reply(user_query: str, reply: str) -> str:
    """Run output guardrails on assistant text before display."""
    output_result = check_output(user_query, reply)
    return output_result.response


inject_styles()
init_session_state()

# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### ✈️ Voyager AI")
    st.caption("Your friendly multi-agent travel planner")

    st.session_state.username_input = st.text_input(
        "Username",
        value=st.session_state.username_input,
        placeholder="e.g. rahul",
        disabled=st.session_state.chat_started,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Save", use_container_width=True):
            save_username(st.session_state.username_input)
            st.rerun()
    with c2:
        if st.button("🔄 Switch", use_container_width=True):
            st.session_state.chat_started = False
            st.session_state.username_input = ""
            st.session_state.saved_username = ""
            st.session_state.thread_id = ""
            st.session_state.chat_messages = []
            st.session_state.last_plan = None
            st.session_state.welcome_shown = False
            st.session_state.last_download = None
            st.session_state.pending_query = None
            st.session_state.processing_phase = None
            st.rerun()

    if st.session_state.chat_started:
        st.success(f"Hi, **{st.session_state.saved_username}**!")
        st.caption(f"Session: `{st.session_state.thread_id}`")
        active_plan = st.session_state.last_plan or load_user_plan(
            st.session_state.saved_username,
            st.session_state.thread_id,
        )
        if active_plan:
            st.session_state.last_plan = active_plan
            dest = active_plan.get("destination", "—")
            st.info(f"Saved plan destination: **{dest or '—'}**")
    else:
        st.info("Save your username to start chatting.")

    st.divider()
    if st.session_state.get("last_download"):
        st.download_button(
            "⬇️ Download last plan",
            data=st.session_state.last_download["content"],
            file_name=st.session_state.last_download["filename"],
            mime="text/markdown",
            use_container_width=True,
        )
    st.markdown("**How it works**")
    st.markdown("1. Ask for a **new trip** → all agents run")
    st.markdown("2. Ask **follow-ups** → answered from your saved plan")
    st.markdown("3. Switch user → each user keeps their own plan in Neon")
    st.divider()
    if guardrails_enabled():
        st.markdown("**🛡️ Guardrails:** enabled (NeMo + Groq)")
        st.caption("Input/output safety checks run before agents and before replies.")
    else:
        st.caption("Guardrails disabled (set GUARDRAILS_ENABLED=true in .env)")
    st.divider()
    if memory_manager.config.mem0_enabled:
        st.markdown("**🧠 Long-term memory:** Mem0 enabled")
        st.caption(f"Retrieves top {memory_manager.config.memory_top_k} user preferences per trip.")
    else:
        st.caption("Mem0 off — add MEM0_API_KEY to .env for cross-session memory")
    st.divider()
    from observability import get_langsmith_status

    ls_status = get_langsmith_status()
    if ls_status.get("enabled"):
        st.markdown("**📊 LangSmith:** enabled")
        st.caption(f"Project: `{ls_status.get('project', 'default')}` — traces at smith.langchain.com")
    else:
        st.caption("LangSmith tracing off (set LANGSMITH_TRACING=true in .env)")

# ---------------- Main ----------------
st.markdown(
    '<div class="hero-card"><h2 style="margin:0;color:#f8fbff;">Voyager AI Travel Chat</h2>'
    "<p style='color:#9fb2cc;margin:0.4rem 0 0;'>Plan trips with specialist agents — "
    "or ask quick follow-ups without re-planning.</p></div>",
    unsafe_allow_html=True,
)

if not st.session_state.chat_started:
    st.warning("👈 Enter your username in the sidebar and click **Save** to begin.")
    st.stop()

show_welcome_if_needed()

# Render chat history
for message in st.session_state.chat_messages:
    avatar = "🧳" if message["role"] == "user" else "✈️"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if message.get("message_type") == "follow_up":
            st.markdown('<span class="follow-up-badge">Answered from memory</span>', unsafe_allow_html=True)
        if message.get("message_type") == "no_plan":
            st.markdown('<span class="follow-up-badge">No plan yet — quick reply</span>', unsafe_allow_html=True)
        if message["role"] == "assistant" and message.get("agents"):
            st.markdown("---")
            st.caption("Agent details")
            render_agent_cards(message["agents"])

# Quick prompts
st.caption("Quick ideas")
chip_cols = st.columns(len(QUICK_PROMPTS))
for col, prompt in zip(chip_cols, QUICK_PROMPTS):
    with col:
        if st.button(prompt, key=f"chip_{prompt}", use_container_width=True):
            st.session_state.pending_prompt = prompt

if st.session_state.get("pending_query"):
    st.info("🔄 Voyager AI is running — you'll see the response when agents finish.")

user_query = st.chat_input(
    "Plan a new trip, or ask about your current plan...",
    disabled=bool(st.session_state.get("pending_query")),
)
user_query = user_query or st.session_state.pop("pending_prompt", None)

# Step 1: user just sent a message — show it immediately on next paint.
if user_query:
    st.session_state.chat_messages.append({"role": "user", "content": user_query})
    st.session_state.pending_query = user_query
    st.session_state.processing_phase = "thinking"
    st.rerun()

# Step 2: paint running UI first (fast rerun), then do heavy work on next rerun.
if st.session_state.get("pending_query") and st.session_state.get("processing_phase") == "thinking":
    active_query = st.session_state.pending_query
    with st.chat_message("assistant", avatar="✈️"):
        render_thinking_indicator(thinking_label_for_query(active_query))
        st.caption("Please wait — Voyager AI is working on your request.")
    st.session_state.processing_phase = "running"
    st.rerun()

# Step 3: run agents / LLM while keeping running status visible.
if st.session_state.get("pending_query") and st.session_state.get("processing_phase") == "running":
    active_query = st.session_state.pending_query
    thinking_label = thinking_label_for_query(active_query)

    with st.chat_message("assistant", avatar="✈️"):
        with st.status("🔄 Voyager AI is running…", expanded=True) as run_status:
            st.caption(thinking_label)
            thinking_slot = st.empty()
            with thinking_slot.container():
                render_thinking_indicator(thinking_label)

            try:
                result = process_pending_query(active_query, thinking_slot=thinking_slot)
            except Exception as exc:
                import traceback
                logging.exception("Trip planning failed")
                detail = str(exc).strip() or type(exc).__name__
                result = {
                    "content": f"Something went wrong while planning your trip: {detail}",
                    "message_type": "error",
                    "agents": None,
                }

            thinking_slot.empty()
            run_status.update(label="✅ Response ready", state="complete", expanded=False)
            st.markdown(result["content"])
            if result.get("message_type") == "follow_up":
                st.markdown(
                    '<span class="follow-up-badge">Answered from memory</span>',
                    unsafe_allow_html=True,
                )
            if result.get("message_type") == "no_plan":
                st.markdown(
                    '<span class="follow-up-badge">No plan yet — quick reply</span>',
                    unsafe_allow_html=True,
                )
            if result.get("message_type") == "guardrail_blocked":
                st.markdown(
                    '<span class="follow-up-badge">Blocked by safety guardrails</span>',
                    unsafe_allow_html=True,
                )

        # Agent cards use st.status (expander-like) — must render outside the run status block.
        if result.get("agents"):
            st.markdown("---")
            st.caption("Agent details")
            render_agent_cards(result["agents"])

    append_assistant_message(
        result["content"],
        message_type=result.get("message_type", "text"),
        agents=result.get("agents"),
    )
    st.session_state.pending_query = None
    st.session_state.processing_phase = None
    st.rerun()
