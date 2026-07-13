"""Tests for turning negatively rated traces into proposed eval cases."""

from evals.helpers.trace_to_golden import (
    build_proposal,
    collect_negative_feedback,
    diagnose_failure,
)


def _trace(*, tags=None, children=None):
    return {
        "id": "11111111-1111-4111-8111-111111111111",
        "name": "travel_planning",
        "inputs": {"user_query": "Plan a 5-day vegetarian trip to Tokyo with flights."},
        "outputs": {"itinerary": "A five-day Tokyo itinerary."},
        "tags": tags or ["streamlit", "trip-planning"],
        "extra": {"metadata": {"user_id": "rahul", "thread_id": "rahul_chat"}},
        "child_runs": children or [],
    }


def test_diagnose_missing_flights_points_to_flight_agent():
    diagnosis = diagnose_failure(
        _trace(children=[{"name": "tavily_search", "run_type": "tool"}]),
        "The plan did not include any flight options.",
    )

    assert diagnosis["component"] == "flight_agent"
    assert diagnosis["failure_type"] == "missing_tool_or_result"
    assert "list_airports" in diagnosis["suggested_checks"]


def test_build_proposal_creates_nightly_case_and_review_envelope():
    proposal = build_proposal(
        _trace(),
        comment="The itinerary ignored my budget.",
        score=0,
    )

    assert proposal["schema_version"] == 1
    assert proposal["review_status"] == "draft"
    assert proposal["diagnosis"]["component"] == "planner_agent"
    assert proposal["target_dataset"] == "golden_nightly.json"
    assert proposal["proposed_golden"]["input"].startswith("Plan a 5-day")
    assert proposal["source"]["run_id"] == "11111111-1111-4111-8111-111111111111"


def test_follow_up_trace_creates_memory_proposal():
    proposal = build_proposal(
        _trace(tags=["streamlit", "follow-up"]),
        comment="It forgot that I am vegetarian.",
        score=0,
    )

    assert proposal["diagnosis"]["component"] == "memory_retrieval"
    assert proposal["target_dataset"] == "golden_memory.json"
    assert proposal["proposed_golden"]["type"] == "multi_turn_chat"


def test_root_state_uses_itinerary_as_output_not_user_query():
    trace = _trace()
    trace["outputs"] = {
        "user_query": "Plan Tokyo",
        "itinerary": "The actual assistant itinerary",
    }

    proposal = build_proposal(trace, comment="It was incomplete.", score=0)

    assert proposal["proposed_golden"]["task_hint"].startswith("Correct")
    assert proposal["source"]["output_preview"] == "The actual assistant itinerary"


def test_follow_up_generations_are_extracted_and_pii_is_redacted():
    trace = _trace(tags=["streamlit", "follow-up"])
    trace["inputs"] = {"messages": [{"role": "user", "content": "Email me at rahul@example.com"}]}
    trace["outputs"] = {
        "generations": [[{"message": {"content": "Sent details to rahul@example.com"}}]]
    }

    proposal = build_proposal(trace, comment="My phone is +91 98765 43210.", score=0)

    turns = proposal["proposed_golden"]["turns"]
    assert turns[0]["content"] == "Email me at [REDACTED_EMAIL]"
    assert turns[1]["content"] == "Sent details to [REDACTED_EMAIL]"
    assert "[REDACTED_PHONE]" in proposal["source"]["feedback_comment"]


class _OtherProjectClient:
    def __init__(self):
        self.read_calls = 0

    def list_feedback(self, **_kwargs):
        return [{"run_id": "11111111-1111-4111-8111-111111111111", "score": 0}]

    def list_runs(self, **_kwargs):
        return iter(())

    def read_run(self, *_args, **_kwargs):
        self.read_calls += 1
        return _trace()


def test_collector_does_not_export_feedback_from_other_projects(tmp_path):
    client = _OtherProjectClient()

    paths = collect_negative_feedback(
        client=client,
        project="northline-travel",
        output_dir=tmp_path,
    )

    assert paths == []
    assert client.read_calls == 0
