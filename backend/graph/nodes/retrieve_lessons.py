"""Retrieve proven lessons before the planner runs."""

from __future__ import annotations

import logging

from lessons.models import TripContext
from lessons.service import LessonBookService

logger = logging.getLogger(__name__)


def retrieve_lessons_node(state: dict, lesson_book: LessonBookService) -> dict:
    context = TripContext.from_state(state)
    lessons = lesson_book.retrieve_for_planning(context)
    lesson_block = lesson_book.format_lessons_for_prompt(lessons)
    memory_context = state.get("memory_context", "No prior user information stored yet.")
    if lesson_block:
        combined_context = f"{memory_context}\n\n{lesson_block}"
    else:
        combined_context = memory_context

    logger.info("RetrieveLessonsNode: loaded %d lesson(s)", len(lessons))
    return {
        "memory_context": combined_context,
        "lesson_context": lesson_block,
        "lessons_loaded": [
            {
                "lesson_id": str(lesson.lesson_id),
                "lesson": lesson.lesson,
                "category": lesson.category,
                "confidence": lesson.confidence,
            }
            for lesson in lessons
        ],
        "current_step": "retrieve_lessons",
    }
