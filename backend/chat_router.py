"""
chat_router.py
--------------
Decides how to handle each user message in the chat UI.

Message types:
- greeting   -> friendly welcome, no agents
- follow_up  -> answer from previous plan/memory, no agents
- new_plan   -> run full travel agent pipeline
"""

from __future__ import annotations

import re
from enum import Enum


class MessageIntent(str, Enum):
    GREETING = "greeting"
    FOLLOW_UP = "follow_up"
    NEW_PLAN = "new_plan"
    CLARIFY = "clarify"


# Phrases that mean the user is asking about an existing plan (past tense / recall).
FOLLOW_UP_PATTERNS = [
    r"\bwhere\b.*\b(plan|planned|going|trip|travel|destination)\b",
    r"\bwhat\b.*\b(plan|planned|trip|itinerary|destination|hotel|flight|weather)\b",
    r"\b(which|repeat|remind|recall|again|previous|last)\b",
    r"\btell me\b.*\b(about|plan|trip)\b",
    r"\bmy (trip|plan|itinerary|destination)\b",
    r"\bwhere did i\b",
    r"\bwhere i (plan|planned|go|went|travel)\b",
    r"\bwhat did you (suggest|recommend|find)\b",
    r"\bdo you remember\b",
    r"\bshow me (my|the) (plan|itinerary|trip)\b",
]

# Phrases that mean the user wants a fresh travel plan.
NEW_PLAN_PATTERNS = [
    r"\bplan\b.*\b(trip|travel|vacation|holiday|itinerary)\b",
    r"\b(book|visit|explore)\b.*\b(trip|travel)\b",
    r"\b\d+\s*(-)?\s*day",
    r"\b(flight|hotel|itinerary|weather)\b.*\b(for|to)\b",
    r"\bunder\b.*(₹|rs|inr|\$|budget|lakhs?|l)\b",
    r"\b(japan|paris|dubai|bali|tokyo|london|goa|thailand|singapore)\b",
]

GREETING_PATTERNS = [
    r"^(hi|hello|hey|good morning|good evening|namaste)\b",
    r"^how are you\b",
    r"^what can you do\b",
]

CORRECTION_PATTERNS = [
    r"\bactually\b.*\b(prefer|vegan|vegetarian|halal|budget|flight|hotel|direct|avoid|not)\b",
    r"\bnot\s+\w+\s*,?\s*but\b",
    r"\b(please\s+)?remember that\b",
    r"\b(update|change)\s+my\s+preference\b",
    r"\bi prefer\b",
    r"\b(always|never)\s+(choose|suggest|book|include)\b",
    r"\bdo not suggest\b",
]


def is_explicit_correction(text: str) -> bool:
    """True when the user explicitly corrects a durable preference."""
    normalized = (text or "").strip().lower()
    return any(re.search(pattern, normalized) for pattern in CORRECTION_PATTERNS)


def is_retrospective_question(text: str) -> bool:
    """True when the user is asking about a plan that may already exist."""
    for pattern in FOLLOW_UP_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def classify_message(user_query: str, has_previous_plan: bool) -> MessageIntent:
    """
    Classify one chat message.

    Input:
    - user_query: what the user typed
    - has_previous_plan: True if we already generated a plan in this session

    Output:
    - MessageIntent value
    """
    text = (user_query or "").strip().lower()
    if not text:
        return MessageIntent.GREETING

    for pattern in GREETING_PATTERNS:
        if re.search(pattern, text):
            return MessageIntent.GREETING

    # Always detect recall questions first — even with no plan in this session.
    if is_retrospective_question(text):
        return MessageIntent.FOLLOW_UP

    for pattern in NEW_PLAN_PATTERNS:
        if re.search(pattern, text):
            return MessageIntent.NEW_PLAN

    # Short vague message after a plan exists -> likely follow-up.
    if has_previous_plan and len(text.split()) <= 12:
        return MessageIntent.FOLLOW_UP

    # Unclear request — ask for details instead of running all agents.
    return MessageIntent.CLARIFY


def build_welcome_message(username: str) -> str:
    """Friendly first message shown when chat starts."""
    name = username or "traveler"
    return (
        f"Hi **{name}**! 👋 I'm **Northline**, your travel planning assistant.\n\n"
        "Here's how I can help:\n"
        "- **Plan a new trip** — I'll run 4 agents: ✈️ Flights, 🏨 Hotels, 🌤️ Weather, 🗓️ Itinerary\n"
        "- **Ask follow-up questions** — e.g. *\"Where did I plan to go?\"* — I'll answer from your current plan **without** re-running agents\n\n"
        "Try something like: *\"Plan a 7-day Japan trip under ₹2L with flights and hotels\"*"
    )


def build_greeting_reply(username: str) -> str:
    """Short reply for hello / small talk."""
    return (
        f"Hello **{username}**! 😊 I'm ready to help you plan a trip.\n\n"
        "Tell me your destination, number of days, and budget — "
        "or ask me about a plan we already created."
    )


def build_no_plan_reply(username: str) -> str:
    """Friendly reply when user asks about a plan that does not exist yet."""
    return (
        f"Hi **{username}**! 🙂 You haven't created a trip plan in this chat yet.\n\n"
        "I can answer questions like *\"Where did I plan to go?\"* only **after** "
        "we've built a plan together.\n\n"
        "**Want to start?** Try something like:\n"
        "- *Plan a 7-day Japan trip under ₹2L*\n"
        "- *5-day Paris getaway with hotels and flights*"
    )


def build_clarify_reply(username: str) -> str:
    """Ask for trip details when the message is too vague to run agents."""
    return (
        f"I'd love to help, **{username}**! 🌍\n\n"
        "To build a full travel plan, tell me:\n"
        "- **Where** you want to go\n"
        "- **How many days**\n"
        "- **Budget** (optional)\n\n"
        "Example: *Plan a 5-day trip to Paris under ₹1.5L*"
    )
