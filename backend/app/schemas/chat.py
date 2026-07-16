"""Chat API schemas."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SessionRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class SessionResponse(BaseModel):
    username: str
    thread_id: str
    has_plan: bool
    welcome_message: str


class ChatRequest(BaseModel):
    username: str
    thread_id: str
    message: str
    run_id: UUID | None = None


class MemoryUpdateInfo(BaseModel):
    action: Literal["added", "updated"]
    attribute_key: str
    attribute_label: str
    previous_value: str = ""
    new_value: str
    source: str = "profile"


class ChatResponse(BaseModel):
    intent: Literal[
        "greeting",
        "follow_up",
        "new_plan",
        "clarify",
        "blocked",
        "preference_statement",
        "preference_correction",
        "preference_query",
    ]
    message: str
    run_id: str | None = None
    message_type: Literal["welcome", "text", "plan", "follow_up", "clarify", "blocked"] = "text"
    agents: dict[str, Any] | None = None
    guardrail_reason: str | None = None
    memory_update: MemoryUpdateInfo | None = None


class PlanResponse(BaseModel):
    plan: dict[str, Any] | None


class StreamEvent(BaseModel):
    type: str
    data: dict[str, Any]
