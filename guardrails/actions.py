"""Custom NeMo Guardrails actions for Voyager AI."""

from __future__ import annotations

import re
from typing import Optional

from nemoguardrails.actions import action


@action(is_system_action=True)
async def detect_pii_in_input(context: Optional[dict] = None) -> list[str]:
    """Detect PII in user input. Non-empty list triggers the PII refusal flow."""
    user_message = (context or {}).get("user_message", "")

    patterns = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "phone": r"\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
        "credit_card": r"\b(?:\d{4}[\s-]?){3}\d{4}\b",
        "password": r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+",
        "api_key": r"(?i)(api[_\s-]?key|secret[_\s-]?key|token)\s*[:=]\s*[A-Za-z0-9_\-]{8,}",
    }

    return [name for name, pattern in patterns.items() if re.search(pattern, user_message)]


@action(is_system_action=True)
async def sanitize_output(context: Optional[dict] = None) -> list[str]:
    """Detect leaked secrets or harmful content in bot responses."""
    bot_message = ""
    if context:
        bot_message = (
            context.get("bot_message")
            or context.get("response")
            or context.get("last_bot_message")
            or ""
        )

    patterns = {
        "system_prompt_leak": r"(?i)(system prompt|hidden instructions|reveal.{0,20}instructions)",
        "hardcoded_credential": r"(?i)(password|api[_\-]?key|secret|token)\s*[:=]\s*['\"]?\w{4,}",
        "private_key": r"-----BEGIN.{0,20}PRIVATE KEY-----",
        "harmful_instruction": r"(?i)\b(step.?by.?step.*(bomb|malware|ransomware|exploit))\b",
    }

    return [name for name, pattern in patterns.items() if re.search(pattern, bot_message)]
