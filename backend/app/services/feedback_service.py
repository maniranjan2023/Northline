"""Feedback service."""

from __future__ import annotations

import logging

from evals.helpers.trace_to_golden import proposal_from_run
from observability import submit_run_feedback

logger = logging.getLogger(__name__)


def submit_feedback(
    *,
    run_id: str,
    score: int,
    comment: str,
    user_query: str,
    destination: str,
    lesson_book,
) -> dict:
    result = submit_run_feedback(run_id, score=score, comment=comment)
    response = {
        "submitted": bool(result.get("submitted")),
        "score": score,
        "comment": comment.strip(),
        "error": result.get("error"),
    }
    if not response["submitted"]:
        return response

    if score == 1:
        lesson_book.record_positive_feedback(run_id=run_id)
        return response

    if not comment.strip():
        response["error"] = "Comment is required for negative feedback."
        return response

    try:
        proposal, path = proposal_from_run(run_id, comment=comment)
        response["diagnosis"] = proposal["diagnosis"]["component"]
        response["proposal_path"] = str(path)
    except Exception as exc:
        logger.warning("Feedback saved, but golden proposal is pending: %s", exc)
        response["proposal_pending"] = True

    try:
        candidate = lesson_book.record_feedback_candidate(
            comment=comment.strip(),
            run_id=run_id,
            user_query=user_query,
            destination=destination,
        )
        response["candidate_id"] = candidate.get("candidate_id")
        if candidate.get("promoted_lesson_id"):
            response["promoted_lesson_id"] = candidate["promoted_lesson_id"]
    except Exception as exc:
        logger.warning("Feedback saved, but lesson candidate failed: %s", exc)

    return response
