"""Parse and answer generic user profile preferences (not food-only)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from memory.preference_keys import (
    format_attribute_label,
    preference_key_for_category,
    query_tokens,
    slugify_key,
)

FOOD_ALIASES = {
    "vegetarian": "vegetarian",
    "vegeterian": "vegetarian",
    "vegatarian": "vegetarian",
    "vegitarian": "vegetarian",
    "vegan": "vegan",
    "halal": "halal",
    "non-vegetarian": "non-vegetarian",
    "non vegetarian": "non-vegetarian",
    "nonveg": "non-vegetarian",
    "non veg": "non-vegetarian",
    "non-veg": "non-vegetarian",
}

DIETARY_TERM_PATTERN = re.compile(
    r"\b(non[-\s]?veg(?:et|itar|iter)?(?:ian|an)?|vegan|halal|veg(?:et|itar|iter)(?:ian|an))\b",
    re.IGNORECASE,
)

TRIP_HINT_PATTERN = re.compile(
    r"\b(plan|trip|itinerary|flight|hotel|budget|days?|visit|book|travel to|under ₹|under \$)\b",
    re.IGNORECASE,
)

QUESTION_START = re.compile(
    r"^(?:what|which|who|where|when|how|do|does|did|can|could|would|should|is|are|am|tell me)\b",
    re.IGNORECASE,
)

INVALID_VALUE_TOKENS = frozenset(
    {
        "food",
        "sport",
        "sports",
        "preference",
        "prefrence",
        "preernce",
        "prefereance",
        "in food",
        "the food",
        "a food",
        "my food",
        "in sport",
        "the sport",
    }
)


@dataclass(frozen=True)
class ParsedPreference:
    attribute_key: str
    attribute_value: str


@dataclass(frozen=True)
class PreferenceQuery:
    attribute_key: str | None
    category_hint: str | None = None


def _clean_value(value: str) -> str:
    cleaned = " ".join((value or "").strip().split())
    cleaned = re.sub(r"[.!?]+$", "", cleaned).strip()
    return cleaned


def _normalize_food(value: str) -> str | None:
    cleaned = " ".join(value.lower().split())
    if cleaned in FOOD_ALIASES:
        return FOOD_ALIASES[cleaned]
    if re.search(r"\bnon[-\s]?veg", cleaned):
        return "non-vegetarian"
    if re.search(r"\bveg(?:et|itar|iter)(?:ian|an)\b", cleaned) and "non" not in cleaned:
        return "vegetarian"
    if "vegan" in cleaned:
        return "vegan"
    if "halal" in cleaned:
        return "halal"
    return None


def _extract_dietary_term(text: str) -> str | None:
    match = DIETARY_TERM_PATTERN.search(text.lower())
    if not match:
        return None
    return _normalize_food(match.group(0))


def _is_question(text: str) -> bool:
    normalized = " ".join((text or "").strip().lower().split())
    if not normalized:
        return False
    if normalized.endswith("?"):
        return True
    if QUESTION_START.search(normalized):
        return True
    if re.search(r"\bwhat\b.*\b(?:do|did|would|should)\s+i\b", normalized):
        return True
    if re.search(r"\bwhat\s+i\s+like\b", normalized):
        return True
    if re.search(r"\b(?:am|are)\s+i\b", normalized):
        return True
    return False


def is_valid_preference_value(value: str, attribute_key: str = "") -> bool:
    cleaned = _clean_value(value).lower()
    if not cleaned or len(cleaned) < 2:
        return False
    if cleaned in INVALID_VALUE_TOKENS:
        return False
    if re.match(r"^(?:in|at|the|a|an|to|for|with|my|your|on)\s+", cleaned):
        if _normalize_food(cleaned) is None and _extract_dietary_term(cleaned) is None:
            return False
    topic = attribute_key.replace("_preference", "").replace("favorite_", "")
    if topic and cleaned == topic.replace("_", " "):
        return False
    if cleaned in {"food", "sport", "sports", "meal", "meals", "diet", "dietary"}:
        return False
    return True


def _is_trip_related(text: str) -> bool:
    return bool(TRIP_HINT_PATTERN.search(text))


def _finalize_preference(key: str, value: str) -> ParsedPreference | None:
    cleaned = _clean_value(value)
    food = _normalize_food(cleaned) or _extract_dietary_term(cleaned)
    if food:
        cleaned = food
        key = "food_preference"
    if not is_valid_preference_value(cleaned, key):
        return None
    return ParsedPreference(key, cleaned)


def _parse_dietary_statement(text: str) -> ParsedPreference | None:
    normalized = " ".join((text or "").strip().lower().split())
    if not normalized:
        return None

    patterns = [
        r"\b(?:please\s+correct(?:\s+that)?(?:,|:)?\s*)?(?:i\s+)?(?:like|am|prefer|want|need|eat)\s+(?:to\s+be\s+)?(?P<food>vegetarian|vegeterian|vegatarian|vegan|halal|non[-\s]?vegetarian|non[-\s]?veg)\b",
        r"\b(?:actually|correction|correct(?:ion)?)\b.*\b(?:i\s+)?(?:like|am|prefer)\s+(?P<food>vegetarian|vegeterian|vegan|halal|non[-\s]?vegetarian|non[-\s]?veg)\b",
        r"\b(?:i\s+)?(?:am|i'm)\s+a\s+(?P<food>vegetarian|vegeterian|vegan|halal|non[-\s]?vegetarian)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        food_value = _normalize_food(match.group("food"))
        if food_value:
            return ParsedPreference("food_preference", food_value)

    food_value = _extract_dietary_term(normalized)
    if food_value:
        return ParsedPreference("food_preference", food_value)
    return None


def _infer_key_from_statement(text: str, value: str) -> str:
    lower = text.lower()
    food = _normalize_food(value)
    if food or _extract_dietary_term(value):
        return "food_preference"
    if re.search(r"\b(?:want|like|love|prefer|enjoy)\s+to\s+play\b", lower):
        return "favorite_sport"
    if re.search(r"\b(?:sport|sports|game|games|play|playing)\b", lower):
        return "favorite_sport"
    if re.search(r"\b(?:food|eat|diet|dietary|meal)\b", lower):
        return "food_preference"
    if re.search(r"\b(?:flight|flights|airline|seat)\b", lower):
        return "flight_preference"
    if re.search(r"\b(?:hotel|hotels|stay|accommodation)\b", lower):
        return "hotel_preference"
    if re.search(r"\b(?:budget|price|cost)\b", lower):
        return "budget_preference"
    if len(value.split()) <= 4:
        return "favorite_sport"
    return preference_key_for_category(value, prefix="preference")


def parse_preference_statement(text: str) -> ParsedPreference | None:
    """Extract a profile attribute from a preference statement."""
    raw = (text or "").strip()
    if not raw or _is_trip_related(raw) or _is_question(raw):
        return None

    dietary = _parse_dietary_statement(raw)
    if dietary:
        return _finalize_preference(dietary.attribute_key, dietary.attribute_value)

    normalized = " ".join(raw.lower().split())

    structured_patterns: list[tuple[str, str]] = [
        (
            r"\bmy favorite (?P<category>[a-z][a-z\s]{1,30}?) is (?P<value>.+)$",
            "favorite_category",
        ),
        (
            r"\b(?:i\s+)?(?:want|wish|would like) to play (?P<value>.+)$",
            "play",
        ),
        (
            r"\b(?:i\s+)?(?:love|like|prefer|enjoy) playing (?P<value>.+)$",
            "play",
        ),
        (
            r"\b(?:please\s+correct(?:\s+that)?(?:,|:)?\s*)?(?:i\s+)?(?:like|love|prefer|enjoy|want)\s+(?P<value>.+)$",
            "generic_like",
        ),
        (
            r"\b(?:i\s+)?(?:am|i'm)\s+(?:a|an)\s+(?P<value>.+)$",
            "generic_am",
        ),
    ]

    for pattern, kind in structured_patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        if kind == "favorite_category":
            category = match.group("category")
            value = _clean_value(match.group("value"))
            if not value:
                continue
            result = _finalize_preference(preference_key_for_category(category), value)
            if result:
                return result
            continue
        value = _clean_value(match.group("value"))
        if not value or len(value.split()) > 12:
            continue
        if kind == "play":
            result = _finalize_preference("favorite_sport", value)
            if result:
                return result
            continue
        key = _infer_key_from_statement(normalized, value)
        result = _finalize_preference(key, value)
        if result:
            return result

    return None


def parse_preference(text: str) -> ParsedPreference | None:
    raw = (text or "").strip()
    raw = re.sub(r"^(?:hi|hello|hey)[,\s!]+", "", raw, flags=re.IGNORECASE).strip()
    return parse_preference_statement(raw)


def looks_like_preference_statement(text: str) -> bool:
    raw = (text or "").strip()
    if not raw or _is_trip_related(raw) or _is_question(raw):
        return False
    if parse_preference(raw):
        return True
    normalized = raw.lower()
    patterns = [
        r"\bmy favorite\b",
        r"\b(?:i\s+)?(?:like|love|prefer|enjoy)\s+(?!to ask\b)",
        r"\b(?:i\s+)?(?:want|wish|would like)\s+to\s+(?:play|do|try)\b",
        r"\b(?:i\s+)?(?:am|i'm|i m)\s+(?:a|an)\s+(?:vegetarian|vegan|halal|non)",
        r"\bremember that\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)


def looks_like_preference_query(text: str) -> bool:
    normalized = " ".join((text or "").strip().lower().split())
    if not normalized:
        return False
    if re.search(r"\bwhat\b.*\b(plan|trip|itinerary|hotel|flight|destination|weather)\b", normalized):
        return False
    patterns = [
        r"\bwhat(?:'s| is| are)\s+my\b",
        r"\bwhat\s+i\s+like\b",
        r"\bwhat\b.*\b(?:like|prefer|eat|play)\b.*\b(?:food|sport|sports|diet|dietary)\b",
        r"\bwhat\s+.+\s+(?:do\s+)?i\s+(?:like|prefer|enjoy|play)\b",
        r"\bmy\s+.+\s+(?:pref(?:erence|rence)|prefrence|preernce)\b",
        r"\bwhat\s+is\s+my\s+\w+\s+(?:pref(?:erence|rence)|prefrence|preernce)\b",
        r"\bdo i\s+(?:like|prefer|enjoy|play)\b",
        r"\b(?:am|are)\s+i\s+(?:a|an)\b",
        r"\b(?:i'm|i m|i am)\s+(?:a\s+)?(?:vegetarian|vegeterian|vegan|halal|non[-\s]?vegetarian|non[-\s]?veg)\b",
        r"\b(?:vegetarian|vegeterian|vegan|non[-\s]?veg).*\bor\b.*(?:vegetarian|vegeterian|non[-\s]?veg)",
        r"\bwhat\s+(?:food|sport|sports|diet|dietary|color|colour|hobby|hobbies)\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)


def parse_preference_query(text: str) -> PreferenceQuery:
    """Map a recall question to a profile key (best effort)."""
    normalized = " ".join((text or "").strip().lower().split())
    if not normalized:
        return PreferenceQuery(attribute_key=None)

    if re.search(r"\bwhat\b.*\b(plan|trip|itinerary|hotel|flight|destination|weather)\b", normalized):
        return PreferenceQuery(attribute_key=None)

    match = re.search(
        r"\bwhat(?:'s| is| are)?\s+my\s+(?:favorite|favourite)\s+(?P<category>[a-z][a-z\s]{1,24}?)(?:\?|$|\s)",
        normalized,
    )
    if match:
        category = match.group("category").strip()
        return PreferenceQuery(
            attribute_key=preference_key_for_category(category),
            category_hint=category,
        )

    match = re.search(
        r"\bwhat\s+(?P<category>food|diet|dietary|sport|sports|color|colour|movie|movies|music|hobby|hobbies)(?:\s+\w+){0,4}\s+(?:do\s+)?i\s+(?:like|prefer|enjoy|play)\b",
        normalized,
    )
    if match:
        category = match.group("category")
        return PreferenceQuery(
            attribute_key=preference_key_for_category(category),
            category_hint=category,
        )

    match = re.search(r"\bmy\s+(?P<category>[a-z][a-z\s]{1,24}?)\s+(?:pref(?:erence|rence)|prefrence|preernce)\b", normalized)
    if match:
        category = match.group("category").strip()
        return PreferenceQuery(
            attribute_key=preference_key_for_category(category),
            category_hint=category,
        )

    match = re.search(
        r"\bwhat\s+is\s+my\s+(?P<category>food|diet|dietary|sport|sports)\s+(?:pref(?:erence|rence)|prefrence|preernce)\b",
        normalized,
    )
    if match:
        category = match.group("category")
        return PreferenceQuery(
            attribute_key=preference_key_for_category(category),
            category_hint=category,
        )

    match = re.search(r"\bwhat\s+i\s+like\s+(?:in\s+)?(?P<category>food|sport|sports|diet|dietary)\b", normalized)
    if match:
        category = match.group("category")
        return PreferenceQuery(
            attribute_key=preference_key_for_category(category),
            category_hint=category,
        )

    if re.search(r"\b(?:food|diet|dietary|vegetarian|vegan|halal)\b", normalized):
        return PreferenceQuery(attribute_key="food_preference", category_hint="food")

    if re.search(r"\b(?:sport|sports|cricket|football|play)\b", normalized):
        return PreferenceQuery(attribute_key="favorite_sport", category_hint="sport")

    return PreferenceQuery(attribute_key=None)


def resolve_profile_key(query: PreferenceQuery, profile: dict[str, str]) -> str | None:
    """Pick the best matching stored key for a preference question."""
    if not profile:
        return query.attribute_key

    if query.attribute_key and query.attribute_key in profile:
        return query.attribute_key

    if query.category_hint:
        hint = slugify_key(query.category_hint)
        for key in profile:
            if hint in key.replace("_", " "):
                return key
        if hint in {"sport", "sports", "game", "games"}:
            for key in profile:
                if "food" in key:
                    continue
                if "sport" in key or key.startswith("favorite_"):
                    return key

    q_tokens = query_tokens(query.category_hint or "")
    if q_tokens:
        best_key = None
        best_score = 0
        for key, value in profile.items():
            key_tokens = query_tokens(key.replace("_", " "))
            val_tokens = query_tokens(value)
            score = len(q_tokens & (key_tokens | val_tokens))
            if score > best_score:
                best_score = score
                best_key = key
        if best_key:
            return best_key

    return query.attribute_key


def _effective_profile_value(profile: dict[str, str], key: str) -> str | None:
    value = profile.get(key)
    if not value:
        return None
    if not is_valid_preference_value(value, key):
        return None
    return value


def answer_preference_query(profile: dict[str, str], query_text: str) -> str | None:
    """Deterministic answer from structured profile."""
    if not profile:
        return None

    normalized = " ".join((query_text or "").strip().lower().split())
    if re.search(r"\b(?:am|are|i'm|i m)\b.*(?:vegetarian|vegan|halal|non[-\s]?veg)", normalized):
        food = _effective_profile_value(profile, "food_preference")
        if food:
            if food == "non-vegetarian":
                return "You are **non-vegetarian** based on your saved profile."
            return f"You are **{food}** based on your saved profile."
        return None

    parsed_query = parse_preference_query(query_text)
    key = resolve_profile_key(parsed_query, profile)

    if key:
        value = _effective_profile_value(profile, key)
        if value:
            label = format_attribute_label(key)
            if key == "food_preference":
                return f"You like **{value}** food."
            return f"Your {label.lower()} is **{value}**."

    valid_entries = {
        k: v for k, v in profile.items() if is_valid_preference_value(v, k)
    }
    if not valid_entries:
        return None

    if parsed_query.attribute_key is None and not parsed_query.category_hint:
        if len(valid_entries) == 1:
            only_key = next(iter(valid_entries))
            label = format_attribute_label(only_key)
            return f"Your {label.lower()} is **{valid_entries[only_key]}**."

    if not parsed_query.attribute_key and not parsed_query.category_hint:
        lines = ["Here's what I have saved in your profile:"]
        for attr_key in sorted(valid_entries):
            label = format_attribute_label(attr_key)
            lines.append(f"- **{label}**: {valid_entries[attr_key]}")
        return "\n".join(lines)

    return None


# Backward-compatible helpers used in tests
def answer_what_food(profile: dict[str, str]) -> str | None:
    if "food_preference" not in profile:
        return None
    food = profile["food_preference"]
    if food == "non-vegetarian":
        return "You like non-vegetarian food."
    return f"You like {food} food."


def answer_food_preference(profile: dict[str, str]) -> str | None:
    if "food_preference" not in profile:
        return None
    food = profile["food_preference"]
    if food == "non-vegetarian":
        return "You are non-vegetarian based on your latest confirmed preference."
    return f"You are {food} based on your latest confirmed preference."
