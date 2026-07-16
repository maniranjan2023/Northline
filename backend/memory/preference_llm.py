"""Optional LLM fallback for ambiguous preference extraction."""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from memory.preference_keys import slugify_key
from memory.preference_parser import ParsedPreference

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You extract ONE durable user profile preference from a chat message.
Return ONLY valid JSON with this shape:
{"attribute_key": "snake_case_key", "attribute_value": "short value"}

Rules:
- attribute_key must be snake_case, stable, and reusable (examples: food_preference, favorite_sport, favorite_color)
- attribute_value must be the latest preference the user stated
- Ignore greetings and trip-planning requests
- If nothing durable is stated, return {}
"""


async def extract_preference_llm(llm, text: str) -> ParsedPreference | None:
    if llm is None or not (text or "").strip():
        return None
    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=text.strip()),
            ]
        )
        raw = (response.content or "").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        payload = json.loads(match.group(0))
        key = slugify_key(str(payload.get("attribute_key", "")))
        value = " ".join(str(payload.get("attribute_value", "")).split())
        if not key or not value:
            return None
        return ParsedPreference(key, value)
    except Exception as exc:
        logger.warning("LLM preference extraction failed: %s", exc)
        return None
