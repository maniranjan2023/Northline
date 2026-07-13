"""Reviewer-only quality node — learns lessons without rewriting itineraries."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lessons.service import LessonBookService

logger = logging.getLogger(__name__)


def quality_check_node(state: dict, lesson_book: LessonBookService) -> dict:
    run_id = None
    metadata = state.get("metadata") or {}
    if isinstance(metadata, dict):
        run_id = metadata.get("langsmith_run_id")

    review_summary = lesson_book.review_and_learn(state, run_id=run_id)
    findings = review_summary.get("findings", [])
    issue_messages = [finding["problem"] for finding in findings]

    logger.info(
        "ReviewerNode: problems=%d created=%d updated=%d",
        review_summary.get("problems_found", 0),
        len(review_summary.get("lessons_created", [])),
        len(review_summary.get("lessons_updated", [])),
    )

    return {
        "quality_passed": review_summary.get("problems_found", 0) == 0,
        "quality_issues": issue_messages,
        "review_summary": review_summary,
        "revision_hints": "",
        "revision_count": state.get("revision_count", 0),
        "current_step": "quality_check",
    }
