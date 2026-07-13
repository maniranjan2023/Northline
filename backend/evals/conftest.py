"""Pytest configuration for Northline eval suites."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Project root on sys.path so `main`, `guardrails`, etc. import cleanly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evals.reporting.write_results import flush_all_collectors


def pytest_configure(config):
    config.addinivalue_line("markers", "ci: fast custom checks (guardrails, router)")
    config.addinivalue_line("markers", "nightly: DeepEval single-turn agent metrics")
    config.addinivalue_line("markers", "memory: DeepEval multi-turn conversation metrics")
    config.addinivalue_line(
        "markers",
        "live: requires EVAL_LIVE=1, API keys, MCP servers, and database",
    )


def pytest_sessionfinish(session, exitstatus):
    """Write accumulated results to evals/results/*.md after each CLI run."""
    written = flush_all_collectors()
    if written:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            for path in written:
                reporter.write_line(f"\nEval results appended → {path}")


@pytest.fixture(scope="session")
def live_eval_enabled() -> bool:
    return os.getenv("EVAL_LIVE", "").strip().lower() in {"1", "true", "yes"}


@pytest.fixture(scope="session")
def groq_configured() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())
