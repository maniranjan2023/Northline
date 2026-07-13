"""Fast, deterministic checks for the final itinerary."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    issues: tuple[QualityIssue, ...]

    @property
    def revision_hints(self) -> str:
        return "\n".join(f"- {issue.message}" for issue in self.issues)


def _requested_days(query: str) -> int | None:
    match = re.search(r"\b(\d{1,2})\s*(?:-| )?days?\b", query, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _itinerary_day_count(itinerary: str) -> int:
    days = {
        int(value)
        for value in re.findall(r"(?:^|\n)\s*#{0,4}\s*day\s+(\d{1,2})\b", itinerary, re.IGNORECASE)
    }
    return len(days)


def _positive_preference(context: str, preference: str) -> bool:
    if preference not in context:
        return False
    negated = re.search(
        rf"\b(?:not|no|avoid)\s+(?:a\s+)?{re.escape(preference)}\b",
        context,
        re.IGNORECASE,
    )
    return negated is None


def check_itinerary(state: dict) -> QualityReport:
    query = str(state.get("user_query") or "")
    itinerary = str(state.get("itinerary") or "").strip()
    destination = str(state.get("destination") or "").strip()
    memory_context = str(state.get("memory_context") or "")
    issues: list[QualityIssue] = []

    if len(itinerary) < 200:
        issues.append(
            QualityIssue(
                "itinerary_too_short",
                "Expand the itinerary with useful day-by-day details.",
            )
        )

    if destination and destination.lower() not in itinerary.lower():
        issues.append(
            QualityIssue(
                "missing_destination",
                f"Clearly name the destination: {destination}.",
            )
        )

    requested_days = _requested_days(query)
    if requested_days is not None:
        actual_days = _itinerary_day_count(itinerary)
        if actual_days != requested_days:
            issues.append(
                QualityIssue(
                    "day_count_mismatch",
                    f"Provide exactly {requested_days} numbered day sections; found {actual_days}.",
                )
            )

    query_lower = query.lower()
    itinerary_lower = itinerary.lower()
    memory_lower = memory_context.lower()
    if (
        any(token in query_lower for token in ("budget", "under ", "$", "₹", "inr", "usd"))
        and not any(token in itinerary_lower for token in ("budget", "cost", "$", "₹", "inr", "usd"))
    ):
        issues.append(QualityIssue("missing_budget", "Add a clear budget or cost summary."))

    for preference in ("vegetarian", "vegan", "halal"):
        if preference in query_lower:
            required = _positive_preference(query_lower, preference)
        else:
            required = _positive_preference(memory_lower, preference)
        if required and preference not in itinerary_lower:
            issues.append(
                QualityIssue(
                    "missing_preference",
                    f"Respect and explicitly mention the user's {preference} preference.",
                )
            )

    if "flight" in query_lower and "flight" not in itinerary_lower:
        issues.append(QualityIssue("missing_flights", "Include the requested flight guidance."))
    if "hotel" in query_lower and not any(word in itinerary_lower for word in ("hotel", "stay", "accommodation")):
        issues.append(QualityIssue("missing_hotels", "Include the requested hotel guidance."))

    return QualityReport(passed=not issues, issues=tuple(issues))
