"""Structured user profile store — latest-value upserts in Postgres."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from memory.preference_keys import format_attribute_label

logger = logging.getLogger(__name__)

_pool = None
_in_memory: dict[str, dict[str, str]] = {}

DIETARY_TERMS = frozenset({"vegetarian", "non-vegetarian", "non vegetarian", "vegan", "halal"})


def bind_pool(pool) -> None:
    global _pool
    _pool = pool


def _use_in_memory() -> bool:
    return _pool is None


def upsert_attribute(
    user_id: str,
    attribute_key: str,
    attribute_value: str,
    *,
    source: str = "user",
) -> None:
    """Overwrite the latest value for a profile attribute."""
    clean_user = user_id.strip().lower()
    clean_key = attribute_key.strip().lower()
    clean_value = " ".join((attribute_value or "").split())
    if not clean_user or not clean_key or not clean_value:
        return

    if _use_in_memory():
        bucket = _in_memory.setdefault(clean_user, {})
        bucket[clean_key] = clean_value
        return

    now = datetime.now(timezone.utc)
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profile (user_id, attribute_key, attribute_value, source, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, attribute_key)
                DO UPDATE SET
                    attribute_value = EXCLUDED.attribute_value,
                    source = EXCLUDED.source,
                    updated_at = EXCLUDED.updated_at
                """,
                (clean_user, clean_key, clean_value, source, now),
            )


def upsert_and_describe(
    user_id: str,
    attribute_key: str,
    attribute_value: str,
    *,
    source: str = "user",
) -> dict[str, str] | None:
    """Upsert a profile attribute and return a change summary for the UI."""
    clean_user = user_id.strip().lower()
    clean_key = attribute_key.strip().lower()
    clean_value = " ".join((attribute_value or "").split())
    if not clean_user or not clean_key or not clean_value:
        return None

    from memory.preference_parser import is_valid_preference_value

    if not is_valid_preference_value(clean_value, clean_key):
        return None

    previous = get_profile(clean_user).get(clean_key)
    if previous == clean_value:
        return None

    upsert_attribute(clean_user, clean_key, clean_value, source=source)
    label = format_attribute_label(clean_key)
    return {
        "action": "updated" if previous else "added",
        "attribute_key": clean_key,
        "attribute_label": label,
        "previous_value": previous or "",
        "new_value": clean_value,
        "source": source,
    }


def get_profile(user_id: str) -> dict[str, str]:
    clean_user = user_id.strip().lower()
    if not clean_user:
        return {}

    if _use_in_memory():
        return dict(_in_memory.get(clean_user, {}))

    with _pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT attribute_key, attribute_value
                FROM user_profile
                WHERE user_id = %s
                ORDER BY attribute_key
                """,
                (clean_user,),
            )
            rows = cur.fetchall()

    profile: dict[str, str] = {}
    for row in rows:
        if isinstance(row, dict):
            profile[str(row["attribute_key"])] = str(row["attribute_value"])
        else:
            profile[str(row[0])] = str(row[1])
    return profile


def format_profile_block(profile: dict[str, str]) -> str:
    if not profile:
        return ""
    lines = ["User Profile (latest confirmed preferences):"]
    for key in sorted(profile):
        label = format_attribute_label(key)
        lines.append(f"- {label}: {profile[key]}")
    return "\n".join(lines)


def merge_memory_context(profile_block: str, semantic_block: str) -> str:
    """Combine structured profile with Mem0 semantic results."""
    semantic = (semantic_block or "").strip()
    if semantic.startswith("No prior"):
        semantic = ""

    if profile_block and semantic:
        return f"{profile_block}\n\n{semantic}"
    if profile_block:
        return profile_block
    if semantic:
        return semantic
    return "No prior user information stored yet."


def filter_semantic_memories(memories: list[str], profile: dict[str, str]) -> list[str]:
    """Drop stale Mem0 facts that conflict with structured profile values."""
    if not profile:
        return memories

    filtered: list[str] = []
    for memory in memories:
        lower = memory.lower()
        if _conflicts_with_profile(lower, profile):
            continue
        filtered.append(memory)
    return filtered


def _conflicts_with_profile(memory_lower: str, profile: dict[str, str]) -> bool:
    food_pref = profile.get("food_preference", "").lower()
    if food_pref and any(term in memory_lower for term in DIETARY_TERMS):
        if food_pref not in memory_lower:
            return True

    for key, value in profile.items():
        if key == "food_preference":
            continue
        value_lower = value.lower()
        if value_lower and value_lower in memory_lower:
            continue
        topic = key.replace("_", " ")
        topic_tokens = [token for token in topic.split() if len(token) > 3]
        if not topic_tokens:
            continue
        if any(token in memory_lower for token in topic_tokens):
            if value_lower and value_lower not in memory_lower and re.search(
                r"\b(like|prefer|favorite|favourite)\b", memory_lower
            ):
                return True
    return False


def reset_in_memory() -> None:
    """Test helper."""
    _in_memory.clear()
