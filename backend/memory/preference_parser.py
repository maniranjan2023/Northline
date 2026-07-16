"""Parse preference statements/corrections into structured profile attributes."""

from __future__ import annotations

import re
from dataclasses import dataclass

FOOD_VALUES = {
    "vegetarian": "vegetarian",
    "vegan": "vegan",
    "halal": "halal",
    "non-vegetarian": "non-vegetarian",
    "non vegetarian": "non-vegetarian",
    "nonveg": "non-vegetarian",
    "non veg": "non-vegetarian",
    "non-veg": "non-vegetarian",
}


@dataclass(frozen=True)
class ParsedPreference:
    attribute_key: str
    attribute_value: str


def _normalize_food(value: str) -> str | None:
    cleaned = " ".join(value.lower().split())
    if cleaned in FOOD_VALUES:
        return FOOD_VALUES[cleaned]
    if "non" in cleaned and ("veg" in cleaned or "vegetarian" in cleaned):
        return "non-vegetarian"
    if "vegetarian" in cleaned and "non" not in cleaned:
        return "vegetarian"
    if "vegan" in cleaned:
        return "vegan"
    if "halal" in cleaned:
        return "halal"
    return None


def parse_food_preference(text: str) -> ParsedPreference | None:
    """Extract food_preference from user text."""
    normalized = " ".join((text or "").strip().lower().split())
    if not normalized:
        return None

    patterns = [
        r"\b(?:please\s+correct(?:\s+that)?(?:,|:)?\s*)?(?:i\s+)?(?:like|am|prefer|want|need|eat)\s+(?:to\s+be\s+)?(?P<food>vegetarian|vegan|halal|non[-\s]?vegetarian|non[-\s]?veg)\b",
        r"\b(?:actually|correction|correct(?:ion)?)\b.*\b(?:i\s+)?(?:like|am|prefer)\s+(?P<food>vegetarian|vegan|halal|non[-\s]?vegetarian|non[-\s]?veg)\b",
        r"\bnot\s+(?P<neg>vegetarian|vegan|halal)\b.*\b(?:but|i\s+(?:like|am|prefer))\s+(?P<food>vegetarian|vegan|halal|non[-\s]?vegetarian|non[-\s]?veg)\b",
        r"\b(?:i\s+)?(?:am|i'm)\s+a\s+(?P<food>vegetarian|vegan|halal|non[-\s]?vegetarian)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        food_raw = match.groupdict().get("food") or match.group(1)
        food_value = _normalize_food(food_raw or "")
        if food_value:
            return ParsedPreference("food_preference", food_value)

    # Fallback: scan for known dietary terms anywhere in the message
    for term in ("non-vegetarian", "non vegetarian", "non-veg", "vegetarian", "vegan", "halal"):
        if term in normalized:
            food_value = _normalize_food(term)
            if food_value:
                return ParsedPreference("food_preference", food_value)

    return None


def parse_preference(text: str) -> ParsedPreference | None:
    """Parse the first recognized profile attribute from text."""
    return parse_food_preference(text)


def answer_food_preference(profile: dict[str, str]) -> str | None:
    """Deterministic answer when food_preference is stored."""
    food = profile.get("food_preference")
    if not food:
        return None
    if food == "non-vegetarian":
        return "You are non-vegetarian based on your latest confirmed preference."
    return f"You are {food} based on your latest confirmed preference."


def answer_what_food(profile: dict[str, str]) -> str | None:
    food = profile.get("food_preference")
    if not food:
        return None
    if food == "non-vegetarian":
        return "You like non-vegetarian food."
    return f"You like {food} food."
