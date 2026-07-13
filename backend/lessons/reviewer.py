"""Itinerary reviewer — identifies problems and suggested lessons only."""

from __future__ import annotations

import re

from graph.quality.itinerary_checker import check_itinerary
from lessons.categories import ISSUE_CATEGORY_MAP
from lessons.models import ReviewFinding


def _count_day_sections(itinerary: str) -> list[str]:
    return re.findall(r"(?:^|\n)\s*#{0,4}\s*day\s+(\d{1,2})\b", itinerary, re.IGNORECASE)


def _findings_from_checker(state: dict) -> list[ReviewFinding]:
    report = check_itinerary(state)
    findings: list[ReviewFinding] = []
    for issue in report.issues:
        category = ISSUE_CATEGORY_MAP.get(issue.code, "Itinerary Structure")
        findings.append(
            ReviewFinding(
                problem=issue.message,
                reason=f"Deterministic review detected issue code `{issue.code}`.",
                suggested_lesson=issue.message,
                category=category,
            )
        )
    return findings


def _findings_from_heuristics(state: dict) -> list[ReviewFinding]:
    itinerary = str(state.get("itinerary") or "")
    query = str(state.get("user_query") or "").lower()
    findings: list[ReviewFinding] = []

    day_blocks = re.split(r"(?i)(?:^|\n)\s*#{0,4}\s*day\s+\d+", itinerary)
    for index, block in enumerate(day_blocks[1:], start=1):
        activity_count = len(re.findall(r"(?i)\b(visit|explore|tour|museum|temple|park|market)\b", block))
        if activity_count > 6:
            findings.append(
                ReviewFinding(
                    problem=f"Day {index} has too many activities.",
                    reason="More than six major activities were scheduled in one day.",
                    suggested_lesson="Limit major attractions to five per day.",
                    category="Activity Balance",
                )
            )
        if "lunch" not in block.lower() and "dinner" not in block.lower() and "meal" not in block.lower():
            findings.append(
                ReviewFinding(
                    problem=f"Day {index} is missing explicit meal breaks.",
                    reason="No lunch or dinner break was scheduled.",
                    suggested_lesson="Leave time for lunch and dinner on busy sightseeing days.",
                    category="Restaurants",
                )
            )

    if len(_count_day_sections(itinerary)) >= 2 and "rest day" not in itinerary.lower():
        findings.append(
            ReviewFinding(
                problem="The itinerary may be too packed across multiple days.",
                reason="No lighter day or free evening was included in a multi-day plan.",
                suggested_lesson="Leave one free hour every evening on multi-day trips.",
                category="Activity Balance",
            )
        )

    if "weather" in query and "weather" not in itinerary.lower():
        findings.append(
            ReviewFinding(
                problem="Weather guidance is missing from the itinerary.",
                reason="The user asked about weather but the final plan does not mention it.",
                suggested_lesson="Include seasonal weather notes when users ask about forecast or season.",
                category="Weather",
            )
        )

    return findings


def review_itinerary(state: dict) -> list[ReviewFinding]:
    """Review an itinerary without modifying it."""
    findings = _findings_from_checker(state) + _findings_from_heuristics(state)
    deduped: list[ReviewFinding] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        key = (finding.problem.lower(), finding.suggested_lesson.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped
