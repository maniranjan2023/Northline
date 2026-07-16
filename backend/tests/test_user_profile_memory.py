"""Regression tests for structured user profile memory."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from chat_router import (
    MessageIntent,
    classify_message,
    is_explicit_correction,
    is_preference_correction,
    is_preference_query,
)
from memory.memory_manager import MemoryManager
from memory.preference_parser import (
    answer_food_preference,
    answer_preference_query,
    answer_what_food,
    is_valid_preference_value,
    looks_like_preference_query,
    parse_preference,
)
from memory.profile_store import (
    format_profile_block,
    get_profile,
    merge_memory_context,
    reset_in_memory,
    upsert_and_describe,
    upsert_attribute,
)
from memory.provider.base import BaseMemoryProvider, MemoryItem


@pytest.fixture(autouse=True)
def _clean_profile_store():
    reset_in_memory()
    yield
    reset_in_memory()


class _MockProvider(BaseMemoryProvider):
    def __init__(self, memories: list[str] | None = None):
        self.memories = memories or []

    async def search(self, user_id: str, query: str, *, limit: int = 8) -> list[MemoryItem]:
        return [MemoryItem(id=str(index), memory=text) for index, text in enumerate(self.memories[:limit])]

    async def add_messages(self, user_id: str, messages: list[dict[str, str]]) -> dict:
        return {}

    async def add_fact(self, user_id: str, fact: str) -> dict:
        return {}

    async def delete(self, memory_id: str) -> None:
        pass

    async def update(self, memory_id: str, text: str) -> None:
        pass

    async def get_all(self, user_id: str, *, limit: int = 100) -> list[MemoryItem]:
        return []


def test_upsert_and_describe_added_vs_updated():
    added = upsert_and_describe("rahul", "food_preference", "vegetarian")
    assert added is not None
    assert added["action"] == "added"
    assert added["new_value"] == "vegetarian"
    assert added["previous_value"] == ""

    updated = upsert_and_describe("rahul", "food_preference", "non-vegetarian")
    assert updated is not None
    assert updated["action"] == "updated"
    assert updated["previous_value"] == "vegetarian"
    assert updated["new_value"] == "non-vegetarian"

    unchanged = upsert_and_describe("rahul", "food_preference", "non-vegetarian")
    assert unchanged is None


def test_correction_overwrites():
    upsert_attribute("rahul", "food_preference", "vegetarian")
    upsert_attribute("rahul", "food_preference", "non-vegetarian")
    assert get_profile("rahul")["food_preference"] == "non-vegetarian"


def test_multiple_corrections():
    upsert_attribute("rahul", "food_preference", "vegetarian")
    upsert_attribute("rahul", "food_preference", "non-vegetarian")
    upsert_attribute("rahul", "food_preference", "vegetarian")
    assert get_profile("rahul")["food_preference"] == "vegetarian"


def test_preference_query_routing():
    intent = classify_message("What food do I like?", has_previous_plan=False)
    assert intent == MessageIntent.PREFERENCE_QUERY

    intent = classify_message("Am I vegetarian or non-vegetarian?", has_previous_plan=False)
    assert intent == MessageIntent.PREFERENCE_QUERY


def test_preference_statement_routing():
    intent = classify_message("I like vegetarian", has_previous_plan=False)
    assert intent == MessageIntent.PREFERENCE_STATEMENT

    intent = classify_message("hey , i like vegeterian", has_previous_plan=True)
    assert intent == MessageIntent.PREFERENCE_STATEMENT


def test_greeting_with_preference_is_not_greeting():
    assert classify_message("hey", has_previous_plan=False) == MessageIntent.GREETING
    assert classify_message("hey , i like vegeterian", has_previous_plan=False) == MessageIntent.PREFERENCE_STATEMENT


def test_preference_query_with_typo():
    intent = classify_message("what food prefrence i like?", has_previous_plan=True)
    assert intent == MessageIntent.PREFERENCE_QUERY


def test_parse_vegeterian_typo():
    parsed = parse_preference("hey , i like vegeterian")
    assert parsed is not None
    assert parsed.attribute_value == "vegetarian"


def test_parse_cricket_sport_preference():
    parsed = parse_preference("I want to play cricket")
    assert parsed is not None
    assert parsed.attribute_key == "favorite_sport"
    assert parsed.attribute_value == "cricket"

    parsed = parse_preference("I like cricket")
    assert parsed is not None
    assert parsed.attribute_key == "favorite_sport"
    assert parsed.attribute_value == "cricket"


def test_answer_sport_preference_query():
    profile = {"favorite_sport": "cricket", "food_preference": "vegetarian"}
    reply = answer_preference_query(profile, "what is my favorite sport?")
    assert reply is not None
    assert "cricket" in reply

    reply = answer_preference_query(profile, "what food prefrence i like?")
    assert reply is not None
    assert "vegetarian" in reply


def test_my_favorite_sport_is():
    parsed = parse_preference("My favorite sport is cricket")
    assert parsed is not None
    assert parsed.attribute_key == "favorite_sport"
    assert parsed.attribute_value == "cricket"


def test_correction_pattern_please_correct():
    text = "Please correct, I like non-vegetarian"
    assert is_preference_correction(text)
    assert is_explicit_correction(text)

    parsed = parse_preference(text)
    assert parsed is not None
    assert parsed.attribute_key == "food_preference"
    assert parsed.attribute_value == "non-vegetarian"


def test_parse_preference_variants():
    cases = [
        ("I am vegetarian", "vegetarian"),
        ("I prefer vegan food", "vegan"),
        ("I like halal", "halal"),
        ("Actually I like non-veg", "non-vegetarian"),
    ]
    for message, expected in cases:
        parsed = parse_preference(message)
        assert parsed is not None, message
        assert parsed.attribute_value == expected, message


def test_deterministic_preference_answers():
    profile = {"food_preference": "non-vegetarian"}
    assert "non-vegetarian" in answer_what_food(profile)
    assert "non-vegetarian" in answer_food_preference(profile)


def test_retrieval_includes_profile_with_trip():
    upsert_attribute("rahul", "food_preference", "vegetarian")
    provider = _MockProvider(memories=["User enjoys beach destinations"])
    mm = MemoryManager(llm=None, provider=provider)

    context = asyncio.run(mm.load_memory_context("rahul", "Plan Bali for 5 days"))

    assert "User Profile" in context
    assert "vegetarian" in context
    assert "beach" in context.lower()


def test_retrieval_filters_stale_dietary_mem0_facts():
    upsert_attribute("rahul", "food_preference", "non-vegetarian")
    provider = _MockProvider(memories=["User is vegetarian", "Prefers direct flights"])
    mm = MemoryManager(llm=None, provider=provider)

    context = asyncio.run(mm.load_memory_context("rahul", "Plan Tokyo"))

    assert "non-vegetarian" in context
    assert "User is vegetarian" not in context
    assert "direct flights" in context


def test_format_and_merge_profile_block():
    profile = {"food_preference": "vegan"}
    block = format_profile_block(profile)
    merged = merge_memory_context(block, "Known User Information\n- Likes museums")
    assert block in merged
    assert "museums" in merged


def test_answer_follow_up_uses_profile(monkeypatch):
    upsert_attribute("rahul", "food_preference", "non-vegetarian")

    captured: dict[str, str] = {}

    class _FakeResponse:
        content = "You are non-vegetarian based on your profile."

    def fake_invoke(messages, config=None):
        captured["prompt"] = messages[-1].content
        return _FakeResponse()

    monkeypatch.setattr("main._llm", lambda: MagicMock(invoke=fake_invoke))
    monkeypatch.setattr(
        "main._memory_manager",
        lambda: MemoryManager(llm=None, provider=_MockProvider()),
    )
    monkeypatch.setattr("main.load_user_plan", lambda *args, **kwargs: None)

    from main import answer_follow_up

    reply = answer_follow_up(
        "Am I vegetarian?",
        "rahul",
        [],
        None,
        "rahul_chat",
    )

    assert "non-vegetarian" in captured["prompt"]
    assert "non-vegetarian" in reply


@pytest.mark.asyncio
async def test_chat_service_preference_statement_persists():
    from app.services.chat_service import handle_chat_message

    memory_manager = MemoryManager(llm=None, provider=_MockProvider())
    username = "test_user_profile_add"
    result = await handle_chat_message(
        username=username,
        thread_id=f"{username}_chat",
        message="I like vegetarian",
        travel_graph=None,
        memory_manager=memory_manager,
        lesson_book=None,
    )

    assert result["intent"] == "preference_statement"
    profile = get_profile(username)
    assert profile.get("food_preference") == "vegetarian"
    if result.get("memory_update"):
        assert result["memory_update"]["action"] in {"added", "updated"}


@pytest.mark.asyncio
async def test_chat_service_preference_query_without_plan():
    from app.services.chat_service import handle_chat_message

    upsert_attribute("rahul", "food_preference", "non-vegetarian")
    memory_manager = MemoryManager(llm=None, provider=_MockProvider())
    result = await handle_chat_message(
        username="rahul",
        thread_id="rahul_chat",
        message="What food do I like?",
        travel_graph=None,
        memory_manager=memory_manager,
        lesson_book=None,
    )

    assert result["intent"] == "preference_query"
    assert "non-vegetarian" in result["message"]


def test_what_i_like_in_food_is_query_not_statement():
    assert looks_like_preference_query("what i like in food?")
    assert parse_preference("what i like in food?") is None
    intent = classify_message("what i like in food?", has_previous_plan=True)
    assert intent == MessageIntent.PREFERENCE_QUERY


def test_invalid_in_food_not_saved():
    assert parse_preference("what i like in food?") is None
    assert not is_valid_preference_value("in food", "food_preference")
    result = upsert_and_describe("rahul", "food_preference", "in food")
    assert result is None


def test_am_i_vegetarian_query():
    intent = classify_message("i m vegeterian or non vegeterian?", has_previous_plan=True)
    assert intent == MessageIntent.PREFERENCE_QUERY

    profile = {"food_preference": "vegetarian"}
    reply = answer_preference_query(profile, "i m vegeterian or non vegeterian?")
    assert reply and "vegetarian" in reply


def test_food_preference_typo_query():
    assert looks_like_preference_query("what is my food preernce?")
    profile = {"food_preference": "vegetarian"}
    reply = answer_preference_query(profile, "what is my food preernce?")
    assert reply and "vegetarian" in reply


def test_corrupted_profile_value_ignored():
    profile = {"food_preference": "in food"}
    reply = answer_preference_query(profile, "what is my food preference?")
    assert reply is None


def test_parse_loves_vegeterian_typo():
    parsed = parse_preference("i loves vegeterian")
    assert parsed is not None
    assert parsed.attribute_key == "food_preference"
    assert parsed.attribute_value == "vegetarian"


def test_loves_vegeterian_routes_as_statement_with_plan():
    intent = classify_message("i loves vegeterian", has_previous_plan=True)
    assert intent == MessageIntent.PREFERENCE_STATEMENT


def test_love_vegetarian_food_parses():
    parsed = parse_preference("I love vegetarian food")
    assert parsed is not None
    assert parsed.attribute_key == "food_preference"
    assert parsed.attribute_value == "vegetarian"


@pytest.mark.asyncio
async def test_user57_flow_save_then_query(monkeypatch):
    """Regression: preference after a plan exists must persist and answer deterministically."""
    from app.services.chat_service import handle_chat_message

    memory_manager = MemoryManager(llm=None, provider=_MockProvider())
    username = "user57"
    thread_id = f"{username}_chat"

    monkeypatch.setattr(
        "app.services.chat_service.user_has_stored_plan",
        lambda *args, **kwargs: True,
    )

    save_result = await handle_chat_message(
        username=username,
        thread_id=thread_id,
        message="i loves vegeterian",
        travel_graph=None,
        memory_manager=memory_manager,
        lesson_book=None,
    )

    assert save_result["intent"] == "preference_statement"
    assert "vegetarian" in save_result["message"].lower()
    profile = get_profile(username)
    assert profile.get("food_preference") == "vegetarian"
    if save_result.get("memory_update"):
        assert save_result["memory_update"]["action"] in {"added", "updated"}

    query_result = await handle_chat_message(
        username=username,
        thread_id=thread_id,
        message="what is my food preference?",
        travel_graph=None,
        memory_manager=memory_manager,
        lesson_book=None,
    )

    assert query_result["intent"] == "preference_query"
    assert "vegetarian" in query_result["message"].lower()
    assert "don't have" not in query_result["message"].lower()
