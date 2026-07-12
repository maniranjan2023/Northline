"""Abstract memory provider — swap Mem0 for another backend without changing graph nodes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class MemoryItem:
    """One retrieved long-term memory."""

    id: str
    memory: str
    score: float | None = None
    metadata: dict[str, Any] | None = None


class BaseMemoryProvider(ABC):
    """Provider interface for long-term memory backends."""

    @abstractmethod
    async def search(self, user_id: str, query: str, *, limit: int = 8) -> list[MemoryItem]:
        """Semantic search for relevant memories."""

    @abstractmethod
    async def add_messages(self, user_id: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Persist a conversation turn; provider may extract facts."""

    @abstractmethod
    async def add_fact(self, user_id: str, fact: str) -> dict[str, Any]:
        """Store one explicit durable fact."""

    @abstractmethod
    async def delete(self, memory_id: str) -> None:
        """Delete a memory by id."""

    @abstractmethod
    async def update(self, memory_id: str, text: str) -> None:
        """Update an existing memory."""

    @abstractmethod
    async def get_all(self, user_id: str, *, limit: int = 100) -> list[MemoryItem]:
        """List memories for a user."""
