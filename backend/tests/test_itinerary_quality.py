"""Tests for deterministic itinerary quality checks."""

from graph.nodes.quality_check import quality_check_node
from graph.quality.itinerary_checker import check_itinerary
from lessons.service import LessonBookService


def _good_itinerary() -> str:
    return """
# Tokyo Travel Plan
## Day 1
Arrive in Tokyo, use the train, and enjoy a vegetarian dinner.
## Day 2
Explore Asakusa and nearby cultural attractions.
## Day 3
Visit museums and local neighborhoods.
## Day 4
Take a day trip and return by train.
## Day 5
Shop, review flight details, and depart.
Budget notes: reserve about $2,000 for flights, hotel, food, and transport.
Hotel notes: choose a central mid-range hotel.
"""


def test_complete_itinerary_passes_deterministic_checks():
    report = check_itinerary(
        {
            "user_query": "Plan a 5-day vegetarian trip to Tokyo under $2000 with flights and hotels.",
            "destination": "Tokyo",
            "itinerary": _good_itinerary(),
            "memory_context": "User prefers vegetarian food.",
        }
    )

    assert report.passed is True
    assert report.issues == ()


def test_missing_budget_and_day_count_are_reported():
    report = check_itinerary(
        {
            "user_query": "Plan a 5-day Tokyo trip under $2000.",
            "destination": "Tokyo",
            "itinerary": "# Tokyo\n## Day 1\nArrive and explore.",
        }
    )

    codes = {issue.code for issue in report.issues}
    assert report.passed is False
    assert "day_count_mismatch" in codes
    assert "missing_budget" in codes


def test_empty_itinerary_fails():
    report = check_itinerary({"user_query": "Plan Paris", "itinerary": ""})

    assert report.passed is False
    assert report.issues[0].code == "itinerary_too_short"


def test_quality_node_reviews_without_rewriting_itinerary():
    service = LessonBookService.in_memory()
    original_itinerary = "Too short."
    result = quality_check_node(
        {
            "user_query": "Plan a 5-day vegetarian trip to Tokyo under $2000 with flights and hotels.",
            "destination": "Tokyo",
            "itinerary": original_itinerary,
            "memory_context": "User prefers vegetarian food.",
            "revision_count": 0,
            "llm_calls": 1,
        },
        lesson_book=service,
    )

    assert "itinerary" not in result
    assert result["quality_passed"] is False
    assert result["review_summary"]["problems_found"] > 0
    assert service._repo.list_lessons()


def test_negated_diet_is_not_enforced_as_positive_preference():
    report = check_itinerary(
        {
            "user_query": "Plan a 5-day trip to Tokyo.",
            "destination": "Tokyo",
            "itinerary": _good_itinerary().replace("vegetarian dinner", "vegan dinner"),
            "memory_context": "User is vegan, not vegetarian.",
        }
    )

    assert all("vegetarian" not in issue.message for issue in report.issues)
