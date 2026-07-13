"""Feedback API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    run_id: str
    score: int = Field(ge=0, le=1)
    comment: str = ""
    user_query: str = ""
    destination: str = ""


class FeedbackResponse(BaseModel):
    submitted: bool
    score: int
    comment: str = ""
    diagnosis: str | None = None
    proposal_path: str | None = None
    proposal_pending: bool = False
    candidate_id: str | None = None
    promoted_lesson_id: str | None = None
    error: str | None = None
