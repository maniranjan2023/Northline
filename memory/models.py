"""
Pydantic models used by the memory system.

These models describe what we store in long-term memory.
We store structured facts, not full raw chat logs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Categories of long-term memory."""

    PREFERENCE = "preference"
    USER_FACT = "user_fact"
    SUCCESS_PATTERN = "success_pattern"
    SUMMARY = "summary"
    FEEDBACK = "feedback"
    TRIP_PLAN = "trip_plan"


class MemoryRecord(BaseModel):
    """One long-term memory item for a user."""

    user_id: str
    memory_type: MemoryType
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = 0.5
    id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RetrievedMemory(BaseModel):
    """A memory item returned from semantic search."""

    record: MemoryRecord
    score: float
