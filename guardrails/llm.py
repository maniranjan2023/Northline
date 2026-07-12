"""Groq LLM helpers for NeMo Guardrails."""

from __future__ import annotations

import os
from typing import Optional

from langchain_groq import ChatGroq

# Small, fast Groq model for guardrail checks (intent, self-check, moderation).
GUARDRAIL_MODEL = os.getenv("GUARDRAIL_MODEL", "llama-3.1-8b-instant")


def get_groq_api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
    return key


def build_guardrail_llm(api_key: Optional[str] = None) -> ChatGroq:
    """Build the Groq guardrail LLM used by NeMo Colang flows and self-checks."""
    return ChatGroq(
        api_key=api_key or get_groq_api_key(),
        model=GUARDRAIL_MODEL,
        temperature=0,
    )
