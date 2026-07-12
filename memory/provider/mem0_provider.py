"""
Mem0 provider — official hosted MemoryClient integration.

Docs: https://docs.mem0.ai/integrations/langgraph
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from memory.config import MemoryConfig
from memory.provider.base import BaseMemoryProvider, MemoryItem

logger = logging.getLogger(__name__)


class Mem0Provider(BaseMemoryProvider):
    """Long-term memory via Mem0 Platform API."""

    def __init__(self, config: MemoryConfig | None = None):
        self._config = config or MemoryConfig.from_env()
        self._client = None

    def _get_client(self):
        if self._client is None:
            from mem0 import MemoryClient

            self._client = MemoryClient(api_key=self._config.mem0_api_key)
        return self._client

    async def search(self, user_id: str, query: str, *, limit: int = 8) -> list[MemoryItem]:
        if not self._config.mem0_enabled:
            return []

        def _search() -> list[MemoryItem]:
            client = self._get_client()
            response = client.search(query, filters={"user_id": user_id}, limit=limit)
            results = response.get("results", response) if isinstance(response, dict) else []
            items: list[MemoryItem] = []
            for row in results or []:
                if isinstance(row, dict):
                    items.append(
                        MemoryItem(
                            id=str(row.get("id", "")),
                            memory=str(row.get("memory", row.get("text", ""))),
                            score=row.get("score"),
                            metadata=row.get("metadata"),
                        )
                    )
            return items

        return await asyncio.to_thread(_search)

    async def add_messages(self, user_id: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self._config.mem0_enabled:
            return {"status": "disabled"}

        def _add() -> dict[str, Any]:
            client = self._get_client()
            return client.add(messages, user_id=user_id)

        return await asyncio.to_thread(_add)

    async def add_fact(self, user_id: str, fact: str) -> dict[str, Any]:
        return await self.add_messages(
            user_id,
            [{"role": "user", "content": fact}],
        )

    async def delete(self, memory_id: str) -> None:
        if not self._config.mem0_enabled:
            return

        def _delete() -> None:
            client = self._get_client()
            client.delete(memory_id)

        await asyncio.to_thread(_delete)

    async def update(self, memory_id: str, text: str) -> None:
        if not self._config.mem0_enabled:
            return

        def _update() -> None:
            client = self._get_client()
            client.update(memory_id, text)

        await asyncio.to_thread(_update)

    async def get_all(self, user_id: str, *, limit: int = 100) -> list[MemoryItem]:
        if not self._config.mem0_enabled:
            return []

        def _get_all() -> list[MemoryItem]:
            client = self._get_client()
            response = client.get_all(filters={"user_id": user_id}, limit=limit)
            results = response.get("results", response) if isinstance(response, dict) else []
            items: list[MemoryItem] = []
            for row in results or []:
                if isinstance(row, dict):
                    items.append(
                        MemoryItem(
                            id=str(row.get("id", "")),
                            memory=str(row.get("memory", row.get("text", ""))),
                            metadata=row.get("metadata"),
                        )
                    )
            return items

        return await asyncio.to_thread(_get_all)
