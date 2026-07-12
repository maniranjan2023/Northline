"""Fast regex safety checks before NeMo Colang / LLM guardrails."""

from __future__ import annotations

import re

UNSAFE_REPLY = (
    "I can't help with hacking, malware, phishing, or any harmful or illegal activity. "
    "I'm here to help you plan safe, legitimate trips."
)

INJECTION_REPLY = (
    "I can't follow instructions that attempt to override my guidelines. "
    "Please ask a normal travel question and I'll be happy to help plan your trip."
)

JAILBREAK_REPLY = (
    "I maintain consistent safety guidelines regardless of how I'm prompted. "
    "How can I help you plan a trip?"
)

TOXIC_REPLY = (
    "I'm here to help respectfully. If you have a travel question, I'm happy to assist — "
    "let's keep things constructive."
)

_PATTERN_GROUPS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "Unsafe",
        re.compile(
            r"(?i)\b(hack(ing)?|crack(ing)?\s+password|malware|phishing|ransomware|"
            r"ddos|make\s+a\s+bomb|steal\s+credit\s+card|break\s+into)\b"
        ),
        UNSAFE_REPLY,
    ),
    (
        "Prompt Injection",
        re.compile(
            r"(?i)(ignore\s+(all\s+)?previous\s+instructions|reveal\s+(your\s+)?system\s+prompt|"
            r"hidden\s+instructions|you\s+are\s+now\s+dan|override\s+(your\s+)?safety)"
        ),
        INJECTION_REPLY,
    ),
    (
        "Jailbreak",
        re.compile(
            r"(?i)(developer\s+mode|no\s+restrictions|jailbreak|bypass\s+(your\s+)?safety|"
            r"god\s+mode|unrestricted\s+ai|evil\s+ai)"
        ),
        JAILBREAK_REPLY,
    ),
    (
        "Toxic",
        re.compile(
            r"(?i)^(you\s+(are\s+)?(stupid|useless|idiot|worthless)|shut\s+up|"
            r"go\s+to\s+hell|you\s+suck)\b"
        ),
        TOXIC_REPLY,
    ),
]


def check_regex_safety(message: str) -> tuple[bool, str, str]:
    """Return (blocked, response, intent) for obvious unsafe patterns."""
    text = (message or "").strip()
    for intent, pattern, reply in _PATTERN_GROUPS:
        if pattern.search(text):
            return True, reply, intent
    return False, "", ""
