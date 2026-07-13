"""Tests for the evidence-backed lesson book."""

from lessons.models import LessonEvidence, TripContext
from lessons.policy import confidence_from_times_seen, is_planning_active, lessons_are_similar
from lessons.reviewer import review_itinerary
from lessons.service import LessonBookService


def test_cannot_create_lesson_without_evidence():
    service = LessonBookService.in_memory()
    try:
        service._repo.create_lesson_with_evidence(
            lesson_text="Keep travel below 3 hours per day.",
            category="Travel Efficiency",
            evidence=LessonEvidence(problem="x", reason="y", observation=""),
            context=TripContext(user_query="Plan Tokyo"),
        )
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_similar_lessons_merge_and_append_evidence():
    service = LessonBookService.in_memory()
    context = TripContext(user_query="Plan Tokyo", destination="Tokyo")
    evidence = LessonEvidence(
        problem="Too much travel",
        reason="Activities far apart",
        observation="Observed in Tokyo itinerary with long transfers.",
    )
    lesson = service._repo.create_lesson_with_evidence(
        lesson_text="Group nearby attractions on the same day.",
        category="Travel Efficiency",
        evidence=evidence,
        context=context,
    )
    updated = service._repo.append_evidence(
        lesson.lesson_id,
        LessonEvidence(
            problem="Too much travel",
            reason="Another long transfer day",
            observation="Second Tokyo itinerary had 4+ hours of transit.",
        ),
    )
    assert updated.times_seen == 2
    assert len(updated.evidence) == 2
    assert updated.confidence == confidence_from_times_seen(2)


def test_only_medium_and_high_lessons_are_used_for_planning():
    service = LessonBookService.in_memory()
    context = TripContext(user_query="Plan Paris", destination="Paris")
    low = service._repo.create_lesson_with_evidence(
        lesson_text="Check museum hours once.",
        category="Opening Hours",
        evidence=LessonEvidence(
            problem="Closed museum",
            reason="Monday closure",
            observation="Seen once.",
        ),
        context=context,
    )
    medium = service._repo.create_lesson_with_evidence(
        lesson_text="Limit attractions to five per day.",
        category="Activity Balance",
        evidence=LessonEvidence(
            problem="Overloaded day",
            reason="Too many stops",
            observation="Seen once.",
        ),
        context=context,
    )
    for _ in range(2):
        service._repo.append_evidence(
            medium.lesson_id,
            LessonEvidence(
                problem="Overloaded day",
                reason="Too many stops",
                observation="Seen again.",
            ),
        )

    lessons = service.retrieve_for_planning(context)
    assert any(item.lesson_id == medium.lesson_id for item in lessons)
    assert all(is_planning_active(item.confidence) for item in lessons)
    assert low.lesson_id not in {item.lesson_id for item in lessons}


def test_feedback_candidate_promotes_after_threshold():
    service = LessonBookService.in_memory()
    for index in range(3):
        result = service.record_feedback_candidate(
            comment="The plan ignored my vegetarian preference.",
            run_id=f"run-{index}",
            user_query="Plan Tokyo vegetarian trip",
            destination="Tokyo",
        )
    assert result["promoted_lesson_id"] is not None
    lessons = service._repo.list_lessons()
    assert len(lessons) == 1
    assert lessons[0].times_seen >= 1


def test_reviewer_does_not_require_itinerary_rewrite():
    state = {
        "user_query": "Plan a 5-day Tokyo trip under $2000 with flights and hotels.",
        "destination": "Tokyo",
        "itinerary": "Short plan.",
        "memory_context": "",
    }
    findings = review_itinerary(state)
    assert findings
    assert all(finding.suggested_lesson for finding in findings)


def test_lessons_are_similar_by_overlap():
    assert lessons_are_similar(
        "Group nearby attractions on the same day.",
        "Group nearby attractions together on one day.",
    )
