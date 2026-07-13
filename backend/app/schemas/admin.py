"""Admin API schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProposalSummary(BaseModel):
    id: str
    filename: str
    run_id: str
    component: str
    target_dataset: str
    feedback_comment: str
    review_status: Literal["pending", "approved", "rejected"]
    created_at: str | None = None


class ProposalDetail(ProposalSummary):
    proposal: dict[str, Any]


class ProposalReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    target_dataset: Literal["ci", "nightly", "memory"] | None = None
    reviewer_note: str = ""


class LessonSummary(BaseModel):
    lesson_id: str
    lesson: str
    category: str
    confidence: float
    times_seen: int
    status: str
    destination: str | None = None


class CandidateSummary(BaseModel):
    candidate_id: str
    suggested_lesson: str
    category: str
    problem: str
    times_seen: int
    confidence: float
    status: str


class ImprovementEvent(BaseModel):
    event_id: str | None = None
    event_type: str
    run_id: str | None = None
    thread_id: str | None = None
    user_id: str | None = None
    payload: dict[str, Any]
    created_at: str | None = None


class SystemStatus(BaseModel):
    guardrails_enabled: bool
    mem0_enabled: bool
    langsmith: dict[str, Any]
