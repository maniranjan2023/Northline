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


class ChatResponse(BaseModel):
    intent: Literal["greeting", "follow_up", "new_plan", "clarify", "blocked"]
    message: str
    run_id: str | None = None
    message_type: Literal["welcome", "text", "plan", "follow_up", "clarify", "blocked"] = "text"
    agents: dict[str, Any] | None = None
    guardrail_reason: str | None = None


class PlanResponse(BaseModel):
    plan: dict[str, Any] | None


class StreamEvent(BaseModel):
    type: str
    data: dict[str, Any]
