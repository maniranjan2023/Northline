"""Inngest client for Northline background / scheduled eval jobs."""

from __future__ import annotations

import logging
import os

import inngest

logger = logging.getLogger("uvicorn.error")

inngest_client = inngest.Inngest(
    app_id="northline",
    logger=logger,
)


def inngest_configured() -> bool:
    """True when Cloud keys are set, or local Dev Server mode is enabled."""
    if os.getenv("INNGEST_DEV", "").strip() in {"1", "true", "True"}:
        return True
    event_key = os.getenv("INNGEST_EVENT_KEY", "").strip()
    signing_key = os.getenv("INNGEST_SIGNING_KEY", "").strip()
    return bool(event_key and signing_key)
