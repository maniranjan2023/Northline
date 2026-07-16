"""Helpers for dynamic profile attribute keys and labels."""

from __future__ import annotations

import re

STOPWORDS = frozenset({"a", "an", "the", "my", "to", "do", "is", "are", "of"})


def slugify_key(text: str, *, max_len: int = 48) -> str:
    """Turn free text into a stable snake_case profile key."""
    value = (text or "").strip().lower()
    value = re.sub(r"[^a-z0-9\s_-]", " ", value)
    value = re.sub(r"[\s-]+", "_", value).strip("_")
    if not value:
        return "preference"
    if len(value) > max_len:
        value = value[:max_len].rstrip("_")
    return value


def format_attribute_label(attribute_key: str) -> str:
    """Human-readable label from any attribute key."""
    key = (attribute_key or "").strip().lower()
    if not key:
        return "Preference"
    return key.replace("_", " ").strip().title()


def normalize_category(category: str) -> str:
    """Singular, slug-safe category token."""
    cat = slugify_key(category, max_len=32)
    if cat.endswith("s") and len(cat) > 4:
        cat = cat[:-1]
    return cat


def preference_key_for_category(category: str, *, prefix: str = "favorite") -> str:
    cat = normalize_category(category)
    if not cat:
        return f"{prefix}_preference"
    if cat in {"food", "diet", "dietary", "meal", "meals"}:
        return "food_preference"
    return f"{prefix}_{cat}"


def query_tokens(text: str) -> set[str]:
    tokens = {
        token
        for token in re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).split()
        if len(token) > 2 and token not in STOPWORDS
    }
    return tokens
