"""Feedback routes."""

from fastapi import APIRouter, Depends

from app.dependencies import get_lesson_book
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.feedback_service import submit_feedback
from lessons.service import LessonBookService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse)
def post_feedback(
    payload: FeedbackRequest,
    lesson_book: LessonBookService = Depends(get_lesson_book),
) -> FeedbackResponse:
    result = submit_feedback(
        run_id=payload.run_id,
        score=payload.score,
        comment=payload.comment,
        user_query=payload.user_query,
        destination=payload.destination,
        lesson_book=lesson_book,
    )
    return FeedbackResponse(**result)
