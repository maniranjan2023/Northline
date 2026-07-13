"""
LangSmith observability bootstrap for Northline.

Official docs (LangGraph + LangChain modules):
https://docs.langchain.com/langsmith/trace-with-langgraph

Required env vars:
  LANGSMITH_TRACING=true
  LANGSMITH_API_KEY=<your-api-key>

Optional:
  LANGSMITH_PROJECT=northline-travel
  LANGSMITH_ENDPOINT=https://api.smith.langchain.com  (EU/APAC: see docs)
  LANGSMITH_WORKSPACE_ID=<workspace-id>
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

import env_loader  # noqa: F401
from langsmith import Client

logger = logging.getLogger(__name__)

_STATUS: dict | None = None


def configure_langsmith() -> dict:
    """
    Enable LangSmith tracing via environment variables.

    LangGraph + LangChain (ChatGroq) calls are traced automatically when enabled.
    """
    global _STATUS
    if _STATUS is not None:
        return _STATUS

    tracing_flag = os.getenv("LANGSMITH_TRACING", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    # Back-compat with older LangChain env name.
    if not tracing_flag:
        tracing_flag = os.getenv("LANGCHAIN_TRACING_V2", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }

    api_key = os.getenv("LANGSMITH_API_KEY", "").strip()
    project = os.getenv("LANGSMITH_PROJECT", "northline-travel").strip() or "northline-travel"
    endpoint = os.getenv("LANGSMITH_ENDPOINT", "").strip()

    if tracing_flag and not api_key:
        logger.warning("LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is missing.")
        _STATUS = {
            "enabled": False,
            "project": project,
            "reason": "missing_api_key",
        }
        return _STATUS

    if tracing_flag and api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ["LANGSMITH_PROJECT"] = project
        if endpoint:
            os.environ["LANGSMITH_ENDPOINT"] = endpoint
        workspace_id = os.getenv("LANGSMITH_WORKSPACE_ID", "").strip()
        if workspace_id:
            os.environ["LANGSMITH_WORKSPACE_ID"] = workspace_id
        # Streamlit reruns quickly — flush traces before the run ends (official guidance).
        os.environ.setdefault("LANGCHAIN_CALLBACKS_BACKGROUND", "false")

    _STATUS = {
        "enabled": bool(tracing_flag and api_key),
        "project": project,
        "endpoint": endpoint or "https://api.smith.langchain.com",
        "reason": "" if tracing_flag and api_key else "disabled",
    }
    return _STATUS


def get_langsmith_status() -> dict:
    """Return cached LangSmith config status."""
    return configure_langsmith()


def submit_run_feedback(
    run_id: UUID | str,
    *,
    score: int,
    comment: str = "",
    client: Any | None = None,
) -> dict:
    """Attach a user's thumbs rating to the exact LangSmith run."""
    if score not in {0, 1}:
        return {"submitted": False, "reason": "invalid_score"}

    try:
        parsed_run_id = UUID(str(run_id))
    except (TypeError, ValueError):
        return {"submitted": False, "reason": "invalid_run_id"}

    status = configure_langsmith()
    if client is None and not status.get("enabled"):
        return {"submitted": False, "reason": "langsmith_disabled"}

    feedback_client = client or Client()
    clean_comment = comment.strip()
    try:
        feedback_client.create_feedback(
            run_id=parsed_run_id,
            key="user_rating",
            score=score,
            comment=clean_comment or None,
            value={"rating": "up" if score == 1 else "down"},
        )
    except Exception as exc:
        logger.warning("LangSmith feedback submission failed: %s", exc)
        return {"submitted": False, "reason": "langsmith_error"}
    return {
        "submitted": True,
        "run_id": str(parsed_run_id),
        "score": score,
    }
