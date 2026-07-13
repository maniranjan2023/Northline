"""High-level lesson book operations."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from lessons.models import LessonEvidence, ReviewFinding, TripContext
from lessons.policy import PROMOTION_THRESHOLD, build_evidence_observation, confidence_label
from lessons.repository import MemoryLessonRepository, PostgresLessonRepository
from lessons.reviewer import review_itinerary

logger = logging.getLogger(__name__)


class LessonBookService:
    """Facade for lesson retrieval, review ingestion, and feedback candidates."""

    def __init__(self, repository) -> None:
        self._repo = repository

    @classmethod
    def from_pool(cls, pool) -> LessonBookService:
        repo = PostgresLessonRepository(pool)
        repo.setup()
        return cls(repo)

    @classmethod
    def in_memory(cls) -> LessonBookService:
        return cls(MemoryLessonRepository())

    def format_lessons_for_prompt(self, lessons) -> str:
        if not lessons:
            return ""
        lines = [
            "Proven planning lessons from past itineraries (guidance only — explicit user requests still win):"
        ]
        for lesson in lessons:
            lines.append(
                f"- [{lesson.category} | {confidence_label(lesson.confidence)}] {lesson.lesson}"
            )
        return "\n".join(lines)

    def retrieve_for_planning(self, context: TripContext, *, limit: int = 8) -> list:
        lessons = self._repo.retrieve_relevant(context, limit=limit)
        self._repo.log_event(
            "lessons_loaded",
            payload={
                "destination": context.destination,
                "lesson_ids": [str(lesson.lesson_id) for lesson in lessons],
                "lessons": [lesson.lesson for lesson in lessons],
            },
        )
        return lessons

    def record_review_findings(
        self,
        state: dict,
        findings: list[ReviewFinding],
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        context = TripContext.from_state(state)
        created: list[str] = []
        updated: list[str] = []
        for finding in findings:
            evidence = LessonEvidence(
                problem=finding.problem,
                reason=finding.reason,
                observation=build_evidence_observation(
                    problem=finding.problem,
                    reason=finding.reason,
                    destination=context.destination,
                ),
                run_id=run_id,
                destination=context.destination or None,
            )
            existing = self._repo.find_similar_lesson(finding.suggested_lesson, finding.category)
            if existing:
                lesson = self._repo.append_evidence(existing.lesson_id, evidence)
                updated.append(str(lesson.lesson_id))
                self._repo.log_event(
                    "lesson_updated",
                    run_id=run_id,
                    thread_id=state.get("thread_id"),
                    user_id=state.get("user_id"),
                    payload={
                        "lesson_id": str(lesson.lesson_id),
                        "confidence": lesson.confidence,
                        "times_seen": lesson.times_seen,
                    },
                )
            else:
                lesson = self._repo.create_lesson_with_evidence(
                    lesson_text=finding.suggested_lesson,
                    category=finding.category,
                    evidence=evidence,
                    context=context,
                )
                created.append(str(lesson.lesson_id))
                self._repo.log_event(
                    "lesson_created",
                    run_id=run_id,
                    thread_id=state.get("thread_id"),
                    user_id=state.get("user_id"),
                    payload={
                        "lesson_id": str(lesson.lesson_id),
                        "category": lesson.category,
                        "confidence": lesson.confidence,
                    },
                )
        summary = {
            "problems_found": len(findings),
            "lessons_created": created,
            "lessons_updated": updated,
            "findings": [
                {
                    "problem": finding.problem,
                    "reason": finding.reason,
                    "suggested_lesson": finding.suggested_lesson,
                    "category": finding.category,
                }
                for finding in findings
            ],
        }
        self._repo.log_event(
            "review_completed",
            run_id=run_id,
            thread_id=state.get("thread_id"),
            user_id=state.get("user_id"),
            payload=summary,
        )
        return summary

    def review_and_learn(self, state: dict, *, run_id: str | None = None) -> dict[str, Any]:
        findings = review_itinerary(state)
        return self.record_review_findings(state, findings, run_id=run_id)

    def record_feedback_candidate(
        self,
        *,
        comment: str,
        run_id: str | None = None,
        user_query: str = "",
        destination: str = "",
    ) -> dict[str, Any]:
        problem = comment.strip()
        reason = "User submitted negative thumbs feedback on the itinerary."
        suggested_lesson = f"Address user concern: {problem}"
        category = "User Preferences"
        candidate = self._repo.upsert_candidate(
            suggested_lesson=suggested_lesson,
            category=category,
            problem=problem,
            reason=reason,
            source="feedback",
            run_id=run_id,
            user_query=user_query,
        )
        promoted_lesson_id = None
        if candidate.times_seen >= PROMOTION_THRESHOLD:
            context = TripContext(user_query=user_query, destination=destination)
            promoted = self._repo.promote_candidate(candidate.candidate_id, context=context)
            if promoted:
                promoted_lesson_id = str(promoted.lesson_id)
                self._repo.log_event(
                    "candidate_promoted",
                    run_id=run_id,
                    payload={
                        "candidate_id": str(candidate.candidate_id),
                        "lesson_id": promoted_lesson_id,
                        "confidence": promoted.confidence,
                    },
                )
        self._repo.log_event(
            "feedback_recorded",
            run_id=run_id,
            payload={
                "candidate_id": str(candidate.candidate_id),
                "times_seen": candidate.times_seen,
                "promoted_lesson_id": promoted_lesson_id,
            },
        )
        return {
            "candidate_id": str(candidate.candidate_id),
            "times_seen": candidate.times_seen,
            "confidence": candidate.confidence,
            "promoted_lesson_id": promoted_lesson_id,
        }

    def record_positive_feedback(self, *, run_id: str | None = None) -> None:
        self._repo.log_event("positive_feedback", run_id=run_id, payload={})

    def get_events(self, *, run_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        return self._repo.list_events(run_id=run_id, limit=limit)

    def get_lesson(self, lesson_id: UUID):
        return self._repo.get_lesson(lesson_id)
