"""Memory module tests."""
import asyncio

from chat_router import is_explicit_correction
from memory.memory_manager import MemoryManager
from memory.provider.base import BaseMemoryProvider, MemoryItem


class _MockProvider(BaseMemoryProvider):
    def __init__(self):
        self.facts = []

    async def search(self, user_id: str, query: str, *, limit: int = 8) -> list[MemoryItem]:
        return []

    async def add_messages(self, user_id: str, messages: list[dict[str, str]]) -> dict:
        return {}

    async def add_fact(self, user_id: str, fact: str) -> dict:
        self.facts.append((user_id, fact))
        return {}

    async def delete(self, memory_id: str) -> None:
        pass

    async def update(self, memory_id: str, text: str) -> None:
        pass

    async def get_all(self, user_id: str, *, limit: int = 100) -> list[MemoryItem]:
        return []


def test_sanitize_user_id():
    mm = MemoryManager(llm=None, provider=_MockProvider())
    assert mm.sanitize_user_id("Rahul-PC") == "rahul-pc"
    assert mm.sanitize_user_id("") == "anonymous"


def test_build_thread_id():
    mm = MemoryManager(llm=None, provider=_MockProvider())
    assert mm.build_thread_id("rahul") == "rahul_chat"
    assert mm.build_thread_id("rahul", "tokyo") == "rahul_trip_tokyo"


def test_explicit_correction_detection():
    assert is_explicit_correction("Actually I am vegan, not vegetarian.")
    assert is_explicit_correction("Please remember that I prefer direct flights.")
    assert not is_explicit_correction("What hotels did you recommend?")


def test_save_explicit_correction_adds_durable_fact():
    provider = _MockProvider()
    mm = MemoryManager(llm=None, provider=provider)

    saved = asyncio.run(
        mm.save_explicit_correction("Rahul", "Actually I prefer budget hotels.")
    )

    assert saved == 1
    assert provider.facts == [
        ("rahul", "User correction: Actually I prefer budget hotels.")
    ]
