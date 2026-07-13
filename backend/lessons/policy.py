"""Confidence, similarity, and promotion rules for lessons."""

from __future__ import annotations

import re
from typing import Iterable

PROMOTION_THRESHOLD = 3
PLANNING_MIN_CONFIDENCE = 0.5
_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "your",
        "when",
        "where",
        "what",
        "how",
        "one",
        "two",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "not",
        "but",
        "can",
        "all",
        "any",
        "per",
    }
)


def normalize_lesson_text(text: str) -> str:
    value = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", value).strip()


def token_set(text: str) -> set[str]:
    return {
        token
        for token in normalize_lesson_text(text).split()
        if len(token) > 2 and token not in _STOP_WORDS
    }


def lessons_are_similar(left: str, right: str, *, threshold: float = 0.55) -> bool:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return (overlap / union) >= threshold


def confidence_from_times_seen(times_seen: int) -> float:
    if times_seen <= 1:
        return 0.2
    if times_seen == 2:
        return 0.35
    if times_seen <= 5:
        return 0.65
    return 0.9


def confidence_label(confidence: float) -> str:
    if confidence < PLANNING_MIN_CONFIDENCE:
        return "low"
    if confidence < 0.8:
        return "medium"
    return "high"


def is_planning_active(confidence: float) -> bool:
    return confidence >= PLANNING_MIN_CONFIDENCE


def build_evidence_observation(
    *,
    problem: str,
    reason: str,
    destination: str = "",
    times_seen: int = 1,
) -> str:
    where = f" in {destination}" if destination else ""
    return (
        f"Observed{where}: {problem}. Reason: {reason}. "
        f"This lesson has now been seen {times_seen} time(s)."
    )


def rank_lessons(lessons: Iterable, context_destination: str = "") -> list:
    ranked = list(lessons)

    def score(lesson) -> tuple[float, int]:
        destination_bonus = 1.0 if context_destination and lesson.destination == context_destination else 0.0
        return (lesson.confidence + destination_bonus, lesson.times_seen)

    ranked.sort(key=score, reverse=True)
    return ranked
