"""Data models for the lesson book."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LessonEvidence:
    problem: str
    reason: str
    observation: str
    run_id: str | None = None
    destination: str | None = None
    evidence_id: UUID = field(default_factory=uuid4)
    lesson_id: UUID | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class Lesson:
    lesson: str
    category: str
    confidence: float = 0.2
    times_seen: int = 1
    status: str = "active"
    destination: str | None = None
    trip_type: str | None = None
    budget_tier: str | None = None
    travel_style: str | None = None
    season: str | None = None
    lesson_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    last_updated: datetime = field(default_factory=utc_now)
    evidence: list[LessonEvidence] = field(default_factory=list)


@dataclass
class CandidateLesson:
    suggested_lesson: str
    category: str
    problem: str
    reason: str
    source: str
    run_id: str | None = None
    user_query: str | None = None
    times_seen: int = 1
    confidence: float = 0.2
    status: str = "candidate"
    candidate_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    last_updated: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ReviewFinding:
    problem: str
    reason: str
    suggested_lesson: str
    category: str


@dataclass
class TripContext:
    user_query: str
    destination: str = ""
    trip_type: str = ""
    budget_tier: str = ""
    travel_style: str = ""
    season: str = ""
    user_preferences: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: dict) -> TripContext:
        query = str(state.get("user_query") or "")
        destination = str(state.get("destination") or "")
        prefs = state.get("user_preferences") or {}
        query_lower = query.lower()
        budget_tier = ""
        if any(token in query_lower for token in ("budget", "under ", "₹", "inr", "$")):
            budget_tier = "budget_conscious"
        travel_style = ""
        if any(token in query_lower for token in ("luxury", "backpack", "family", "romantic")):
            for style in ("luxury", "backpack", "family", "romantic"):
                if style in query_lower:
                    travel_style = style
                    break
        return cls(
            user_query=query,
            destination=destination,
            trip_type="multi_day" if "day" in query_lower else "general",
            budget_tier=budget_tier,
            travel_style=travel_style,
            user_preferences=prefs,
        )
