"""Memory configuration — short-term (PostgresSaver) + long-term (Mem0)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(override=True)


@dataclass(frozen=True)
class MemoryConfig:
    """Runtime memory settings loaded from environment variables."""

    # Mem0 (long-term)
    mem0_api_key: str
    mem0_enabled: bool
    memory_top_k: int

    # Short-term checkpoint (Neon Postgres)
    database_url: str

    @classmethod
    def from_env(cls) -> "MemoryConfig":
        api_key = os.getenv("MEM0_API_KEY", "").strip()
        enabled = os.getenv("MEM0_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        return cls(
            mem0_api_key=api_key,
            mem0_enabled=enabled and bool(api_key),
            memory_top_k=int(os.getenv("MEMORY_TOP_K", "8")),
            database_url=os.getenv("DATABASE_URL", "").strip(),
        )
