"""Lightweight guardrails feature flag (no NeMo import)."""

from __future__ import annotations

import os

import env_loader  # noqa: F401


def guardrails_enabled() -> bool:
    return os.getenv("GUARDRAILS_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
