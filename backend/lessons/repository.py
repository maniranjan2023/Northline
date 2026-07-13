"""Lesson book persistence layer."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from lessons.models import CandidateLesson, Lesson, LessonEvidence, TripContext, utc_now
from lessons.policy import (
    build_evidence_observation,
    confidence_from_times_seen,
    is_planning_active,
    lessons_are_similar,
    rank_lessons,
)

logger = logging.getLogger(__name__)


def _row_to_lesson(row: dict, evidence_rows: list[dict] | None = None) -> Lesson:
    evidence = [
        LessonEvidence(
            evidence_id=UUID(str(item["evidence_id"])),
            lesson_id=UUID(str(item["lesson_id"])),
            problem=item["problem"],
            reason=item.get("reason") or "",
            observation=item["observation"],
            run_id=item.get("run_id"),
            destination=item.get("destination"),
            created_at=item.get("created_at") or utc_now(),
        )
        for item in (evidence_rows or [])
    ]
    return Lesson(
        lesson_id=UUID(str(row["lesson_id"])),
        lesson=row["lesson"],
        category=row["category"],
        confidence=float(row["confidence"]),
        times_seen=int(row["times_seen"]),
        status=row["status"],
        destination=row.get("destination"),
        trip_type=row.get("trip_type"),
        budget_tier=row.get("budget_tier"),
        travel_style=row.get("travel_style"),
        season=row.get("season"),
        created_at=row.get("created_at") or utc_now(),
        last_updated=row.get("last_updated") or utc_now(),
        evidence=evidence,
    )


class MemoryLessonRepository:
    """In-memory repository for tests and local development."""

    def __init__(self) -> None:
        self.lessons: dict[UUID, Lesson] = {}
        self.candidates: dict[UUID, CandidateLesson] = {}
        self.events: list[dict[str, Any]] = []

    def setup(self) -> None:
        return None

    def find_similar_lesson(self, lesson_text: str, category: str) -> Lesson | None:
        for lesson in self.lessons.values():
            if lesson.category == category and lessons_are_similar(lesson.lesson, lesson_text):
                return deepcopy(lesson)
        return None

    def create_lesson_with_evidence(
        self,
        *,
        lesson_text: str,
        category: str,
        evidence: LessonEvidence,
        context: TripContext,
        status: str = "active",
    ) -> Lesson:
        if not evidence.observation.strip():
            raise ValueError("Cannot create a lesson without evidence.")
        lesson = Lesson(
            lesson=lesson_text,
            category=category,
            confidence=confidence_from_times_seen(1),
            times_seen=1,
            status=status,
            destination=context.destination or None,
            trip_type=context.trip_type or None,
            budget_tier=context.budget_tier or None,
            travel_style=context.travel_style or None,
            season=context.season or None,
        )
        evidence.lesson_id = lesson.lesson_id
        lesson.evidence.append(evidence)
        self.lessons[lesson.lesson_id] = deepcopy(lesson)
        return deepcopy(lesson)

    def append_evidence(self, lesson_id: UUID, evidence: LessonEvidence) -> Lesson:
        lesson = self.lessons[lesson_id]
        lesson.times_seen += 1
        lesson.confidence = confidence_from_times_seen(lesson.times_seen)
        lesson.last_updated = utc_now()
        evidence.lesson_id = lesson_id
        lesson.evidence.append(evidence)
        self.lessons[lesson_id] = deepcopy(lesson)
        return deepcopy(lesson)

    def get_lesson(self, lesson_id: UUID) -> Lesson | None:
        lesson = self.lessons.get(lesson_id)
        return deepcopy(lesson) if lesson else None

    def list_lessons(self, *, active_only: bool = True) -> list[Lesson]:
        lessons = [
            deepcopy(lesson)
            for lesson in self.lessons.values()
            if lesson.status == "active" or not active_only
        ]
        return lessons

    def retrieve_relevant(self, context: TripContext, *, limit: int = 8) -> list[Lesson]:
        lessons = [
            lesson
            for lesson in self.list_lessons()
            if is_planning_active(lesson.confidence)
        ]
        filtered = []
        for lesson in lessons:
            if context.destination and lesson.destination and lesson.destination != context.destination:
                continue
            if context.budget_tier and lesson.budget_tier and lesson.budget_tier != context.budget_tier:
                continue
            filtered.append(lesson)
        if not filtered:
            filtered = lessons
        return rank_lessons(filtered, context.destination)[:limit]

    def find_similar_candidate(self, suggested_lesson: str, category: str) -> CandidateLesson | None:
        for candidate in self.candidates.values():
            if candidate.status != "candidate":
                continue
            if candidate.category == category and lessons_are_similar(candidate.suggested_lesson, suggested_lesson):
                return deepcopy(candidate)
        return None

    def upsert_candidate(
        self,
        *,
        suggested_lesson: str,
        category: str,
        problem: str,
        reason: str,
        source: str,
        run_id: str | None = None,
        user_query: str | None = None,
    ) -> CandidateLesson:
        existing = self.find_similar_candidate(suggested_lesson, category)
        if existing:
            candidate = self.candidates[existing.candidate_id]
            candidate.times_seen += 1
            candidate.confidence = confidence_from_times_seen(candidate.times_seen)
            candidate.last_updated = utc_now()
            self.candidates[candidate.candidate_id] = deepcopy(candidate)
            return deepcopy(candidate)

        candidate = CandidateLesson(
            suggested_lesson=suggested_lesson,
            category=category,
            problem=problem,
            reason=reason,
            source=source,
            run_id=run_id,
            user_query=user_query,
        )
        self.candidates[candidate.candidate_id] = deepcopy(candidate)
        return deepcopy(candidate)

    def promote_candidate(self, candidate_id: UUID, *, context: TripContext) -> Lesson | None:
        candidate = self.candidates.get(candidate_id)
        if not candidate or candidate.status != "candidate":
            return None
        evidence = LessonEvidence(
            problem=candidate.problem,
            reason=candidate.reason,
            observation=build_evidence_observation(
                problem=candidate.problem,
                reason=candidate.reason,
                destination=context.destination,
                times_seen=candidate.times_seen,
            ),
            run_id=candidate.run_id,
            destination=context.destination or None,
        )
        existing = self.find_similar_lesson(candidate.suggested_lesson, candidate.category)
        if existing:
            lesson = self.append_evidence(existing.lesson_id, evidence)
        else:
            lesson = self.create_lesson_with_evidence(
                lesson_text=candidate.suggested_lesson,
                category=candidate.category,
                evidence=evidence,
                context=context,
            )
        candidate.status = "promoted"
        candidate.last_updated = utc_now()
        self.candidates[candidate_id] = deepcopy(candidate)
        return lesson

    def log_event(
        self,
        event_type: str,
        *,
        run_id: str | None = None,
        thread_id: str | None = None,
        user_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "run_id": run_id,
                "thread_id": thread_id,
                "user_id": user_id,
                "payload": payload or {},
                "created_at": utc_now().isoformat(),
            }
        )

    def list_events(self, *, run_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        events = self.events
        if run_id:
            events = [event for event in events if event.get("run_id") == run_id]
        return list(reversed(events[-limit:]))


class PostgresLessonRepository(MemoryLessonRepository):
    """PostgreSQL-backed lesson repository."""

    def __init__(self, pool) -> None:
        super().__init__()
        self._pool = pool

    def setup(self) -> None:
        from lessons.schema import setup_lesson_schema

        setup_lesson_schema(self._pool)

    def _fetch_lesson(self, lesson_id: UUID) -> Lesson | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT lesson_id, lesson, category, confidence, times_seen, status,
                           destination, trip_type, budget_tier, travel_style, season,
                           created_at, last_updated
                    FROM lessons WHERE lesson_id = %s
                    """,
                    (str(lesson_id),),
                )
                row = cur.fetchone()
                if not row:
                    return None
                columns = [
                    "lesson_id", "lesson", "category", "confidence", "times_seen", "status",
                    "destination", "trip_type", "budget_tier", "travel_style", "season",
                    "created_at", "last_updated",
                ]
                lesson_row = dict(zip(columns, row))
                cur.execute(
                    """
                    SELECT evidence_id, lesson_id, problem, reason, observation, run_id, destination, created_at
                    FROM lesson_evidence WHERE lesson_id = %s ORDER BY created_at ASC
                    """,
                    (str(lesson_id),),
                )
                evidence_rows = [
                    dict(
                        zip(
                            ["evidence_id", "lesson_id", "problem", "reason", "observation", "run_id", "destination", "created_at"],
                            evidence_row,
                        )
                    )
                    for evidence_row in cur.fetchall()
                ]
        return _row_to_lesson(lesson_row, evidence_rows)

    def get_lesson(self, lesson_id: UUID) -> Lesson | None:
        return self._fetch_lesson(lesson_id)

    def find_similar_lesson(self, lesson_text: str, category: str) -> Lesson | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT lesson_id, lesson FROM lessons WHERE category = %s AND status = 'active'",
                    (category,),
                )
                for lesson_id, existing_lesson in cur.fetchall():
                    if lessons_are_similar(existing_lesson, lesson_text):
                        return self._fetch_lesson(UUID(str(lesson_id)))
        return None

    def create_lesson_with_evidence(
        self,
        *,
        lesson_text: str,
        category: str,
        evidence: LessonEvidence,
        context: TripContext,
        status: str = "active",
    ) -> Lesson:
        if not evidence.observation.strip():
            raise ValueError("Cannot create a lesson without evidence.")
        lesson = Lesson(
            lesson=lesson_text,
            category=category,
            confidence=confidence_from_times_seen(1),
            times_seen=1,
            status=status,
            destination=context.destination or None,
            trip_type=context.trip_type or None,
            budget_tier=context.budget_tier or None,
            travel_style=context.travel_style or None,
            season=context.season or None,
        )
        evidence.lesson_id = lesson.lesson_id
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lessons (
                        lesson_id, lesson, category, confidence, times_seen, status,
                        destination, trip_type, budget_tier, travel_style, season,
                        created_at, last_updated
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        str(lesson.lesson_id), lesson.lesson, lesson.category, lesson.confidence,
                        lesson.times_seen, lesson.status, lesson.destination, lesson.trip_type,
                        lesson.budget_tier, lesson.travel_style, lesson.season,
                        lesson.created_at, lesson.last_updated,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO lesson_evidence (
                        evidence_id, lesson_id, problem, reason, observation, run_id, destination, created_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        str(evidence.evidence_id), str(lesson.lesson_id), evidence.problem,
                        evidence.reason, evidence.observation, evidence.run_id,
                        evidence.destination, evidence.created_at,
                    ),
                )
        return self._fetch_lesson(lesson.lesson_id) or lesson

    def append_evidence(self, lesson_id: UUID, evidence: LessonEvidence) -> Lesson:
        lesson = self._fetch_lesson(lesson_id)
        if not lesson:
            raise KeyError(f"Lesson not found: {lesson_id}")
        times_seen = lesson.times_seen + 1
        confidence = confidence_from_times_seen(times_seen)
        now = utc_now()
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE lessons SET times_seen = %s, confidence = %s, last_updated = %s WHERE lesson_id = %s",
                    (times_seen, confidence, now, str(lesson_id)),
                )
                cur.execute(
                    """
                    INSERT INTO lesson_evidence (
                        evidence_id, lesson_id, problem, reason, observation, run_id, destination, created_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        str(evidence.evidence_id), str(lesson_id), evidence.problem,
                        evidence.reason, evidence.observation, evidence.run_id,
                        evidence.destination, evidence.created_at,
                    ),
                )
        return self._fetch_lesson(lesson_id) or lesson

    def list_lessons(self, *, active_only: bool = True) -> list[Lesson]:
        query = "SELECT lesson_id FROM lessons"
        if active_only:
            query += " WHERE status = 'active'"
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                lesson_ids = [UUID(str(row[0])) for row in cur.fetchall()]
        return [lesson for lesson_id in lesson_ids if (lesson := self._fetch_lesson(lesson_id))]

    def retrieve_relevant(self, context: TripContext, *, limit: int = 8) -> list[Lesson]:
        lessons = [
            lesson for lesson in self.list_lessons() if is_planning_active(lesson.confidence)
        ]
        filtered = []
        for lesson in lessons:
            if context.destination and lesson.destination and lesson.destination != context.destination:
                continue
            if context.budget_tier and lesson.budget_tier and lesson.budget_tier != context.budget_tier:
                continue
            filtered.append(lesson)
        if not filtered:
            filtered = lessons
        return rank_lessons(filtered, context.destination)[:limit]

    def find_similar_candidate(self, suggested_lesson: str, category: str) -> CandidateLesson | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT candidate_id, suggested_lesson, category, problem, reason, source,
                           run_id, user_query, times_seen, confidence, status, created_at, last_updated
                    FROM candidate_lessons WHERE status = 'candidate' AND category = %s
                    """,
                    (category,),
                )
                for row in cur.fetchall():
                    candidate = CandidateLesson(
                        candidate_id=UUID(str(row[0])),
                        suggested_lesson=row[1],
                        category=row[2],
                        problem=row[3],
                        reason=row[4] or "",
                        source=row[5],
                        run_id=row[6],
                        user_query=row[7],
                        times_seen=int(row[8]),
                        confidence=float(row[9]),
                        status=row[10],
                        created_at=row[11] or utc_now(),
                        last_updated=row[12] or utc_now(),
                    )
                    if lessons_are_similar(candidate.suggested_lesson, suggested_lesson):
                        return candidate
        return None

    def upsert_candidate(
        self,
        *,
        suggested_lesson: str,
        category: str,
        problem: str,
        reason: str,
        source: str,
        run_id: str | None = None,
        user_query: str | None = None,
    ) -> CandidateLesson:
        existing = self.find_similar_candidate(suggested_lesson, category)
        now = utc_now()
        if existing:
            times_seen = existing.times_seen + 1
            confidence = confidence_from_times_seen(times_seen)
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE candidate_lessons
                        SET times_seen = %s, confidence = %s, last_updated = %s
                        WHERE candidate_id = %s
                        """,
                        (times_seen, confidence, now, str(existing.candidate_id)),
                    )
            existing.times_seen = times_seen
            existing.confidence = confidence
            existing.last_updated = now
            return existing

        candidate = CandidateLesson(
            suggested_lesson=suggested_lesson,
            category=category,
            problem=problem,
            reason=reason,
            source=source,
            run_id=run_id,
            user_query=user_query,
        )
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO candidate_lessons (
                        candidate_id, suggested_lesson, category, problem, reason, source,
                        run_id, user_query, times_seen, confidence, status, created_at, last_updated
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        str(candidate.candidate_id), candidate.suggested_lesson, candidate.category,
                        candidate.problem, candidate.reason, candidate.source, candidate.run_id,
                        candidate.user_query, candidate.times_seen, candidate.confidence,
                        candidate.status, candidate.created_at, candidate.last_updated,
                    ),
                )
        return candidate

    def promote_candidate(self, candidate_id: UUID, *, context: TripContext) -> Lesson | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT candidate_id, suggested_lesson, category, problem, reason, source,
                           run_id, user_query, times_seen, confidence, status
                    FROM candidate_lessons WHERE candidate_id = %s
                    """,
                    (str(candidate_id),),
                )
                row = cur.fetchone()
        if not row or row[10] != "candidate":
            return None
        candidate = CandidateLesson(
            candidate_id=UUID(str(row[0])),
            suggested_lesson=row[1],
            category=row[2],
            problem=row[3],
            reason=row[4] or "",
            source=row[5],
            run_id=row[6],
            user_query=row[7],
            times_seen=int(row[8]),
            confidence=float(row[9]),
            status=row[10],
        )
        evidence = LessonEvidence(
            problem=candidate.problem,
            reason=candidate.reason,
            observation=build_evidence_observation(
                problem=candidate.problem,
                reason=candidate.reason,
                destination=context.destination,
                times_seen=candidate.times_seen,
            ),
            run_id=candidate.run_id,
            destination=context.destination or None,
        )
        existing = self.find_similar_lesson(candidate.suggested_lesson, candidate.category)
        lesson = (
            self.append_evidence(existing.lesson_id, evidence)
            if existing
            else self.create_lesson_with_evidence(
                lesson_text=candidate.suggested_lesson,
                category=candidate.category,
                evidence=evidence,
                context=context,
            )
        )
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE candidate_lessons SET status = 'promoted', last_updated = %s WHERE candidate_id = %s",
                    (utc_now(), str(candidate_id)),
                )
        return lesson

    def log_event(
        self,
        event_type: str,
        *,
        run_id: str | None = None,
        thread_id: str | None = None,
        user_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO improvement_events (event_id, event_type, run_id, thread_id, user_id, payload, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
                    """,
                    (
                        str(uuid4()), event_type, run_id, thread_id, user_id,
                        json.dumps(payload or {}), utc_now(),
                    ),
                )

    def list_events(self, *, run_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = """
            SELECT event_id, event_type, run_id, thread_id, user_id, payload, created_at
            FROM improvement_events
        """
        params: list[Any] = []
        if run_id:
            query += " WHERE run_id = %s"
            params.append(run_id)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [
            {
                "event_id": str(row[0]),
                "event_type": row[1],
                "run_id": row[2],
                "thread_id": row[3],
                "user_id": row[4],
                "payload": row[5] if isinstance(row[5], dict) else json.loads(row[5] or "{}"),
                "created_at": row[6].isoformat() if isinstance(row[6], datetime) else row[6],
            }
            for row in rows
        ]
