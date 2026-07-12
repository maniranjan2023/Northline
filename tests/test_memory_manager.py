"""Memory module tests."""

from memory.memory_manager import MemoryManager
from memory.provider.base import BaseMemoryProvider, MemoryItem


class _MockProvider(BaseMemoryProvider):
    async def search(self, user_id: str, query: str, *, limit: int = 8) -> list[MemoryItem]:
        return []

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


def test_sanitize_user_id():
    mm = MemoryManager(llm=None, provider=_MockProvider())
    assert mm.sanitize_user_id("Rahul-PC") == "rahul-pc"
    assert mm.sanitize_user_id("") == "anonymous"


def test_build_thread_id():
    mm = MemoryManager(llm=None, provider=_MockProvider())
    assert mm.build_thread_id("rahul") == "rahul_chat"
    assert mm.build_thread_id("rahul", "tokyo") == "rahul_trip_tokyo"
