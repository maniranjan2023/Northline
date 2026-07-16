"""Smoke tests for eval runner + Inngest wiring."""

from __future__ import annotations

from app.inngest_client import inngest_client, inngest_configured
from app.inngest_fns import EVENT_BY_SUITE, INNGEST_FUNCTIONS
from app.schemas.eval import EvalRunRequest
from app.services.eval_runner_service import EVENT_BY_SUITE as SERVICE_EVENTS
from app.services.eval_runner_service import SCHEDULES, get_capabilities


def test_eval_run_request_defaults_to_all():
    assert EvalRunRequest().suite == "all"
    assert EvalRunRequest(suite="ci").suite == "ci"


def test_inngest_functions_registered():
    assert len(INNGEST_FUNCTIONS) == 4
    assert inngest_client.app_id == "northline"


def test_event_names_match_service():
    assert EVENT_BY_SUITE == SERVICE_EVENTS
    assert set(EVENT_BY_SUITE) == {"ci", "single_turn", "multi_turn", "all"}


def test_schedules_cover_three_suites():
    assert set(SCHEDULES) == {"ci", "single_turn", "multi_turn"}
    assert "12:00" in SCHEDULES["ci"]["label"]
    assert "18:00" in SCHEDULES["single_turn"]["label"]
    assert "22:00" in SCHEDULES["multi_turn"]["label"]


def test_capabilities_shape():
    caps = get_capabilities()
    assert "eval_deps_installed" in caps
    assert "inngest_configured" in caps
    assert caps["inngest_configured"] is inngest_configured()
    assert "ci" in caps["suites"]
    assert caps["suites"]["ci"]["schedule"]["timezone"] == "Asia/Kolkata"
