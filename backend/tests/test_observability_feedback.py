"""Tests for LangSmith feedback submission."""

from uuid import uuid4

from observability import submit_run_feedback


class _FeedbackClient:
    def __init__(self):
        self.calls = []

    def create_feedback(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "feedback-1"}


class _FailingFeedbackClient:
    def create_feedback(self, **_kwargs):
        raise RuntimeError("network unavailable")


def test_submit_run_feedback_links_score_and_comment_to_run():
    client = _FeedbackClient()
    run_id = uuid4()

    result = submit_run_feedback(
        run_id,
        score=0,
        comment="The flight options were missing.",
        client=client,
    )

    assert result["submitted"] is True
    assert result["run_id"] == str(run_id)
    assert client.calls == [
        {
            "run_id": run_id,
            "key": "user_rating",
            "score": 0,
            "comment": "The flight options were missing.",
            "value": {"rating": "down"},
        }
    ]


def test_submit_run_feedback_rejects_invalid_score():
    client = _FeedbackClient()

    result = submit_run_feedback(uuid4(), score=2, client=client)

    assert result["submitted"] is False
    assert result["reason"] == "invalid_score"
    assert client.calls == []


def test_submit_run_feedback_returns_failure_for_client_error():
    result = submit_run_feedback(
        uuid4(),
        score=0,
        comment="Missing hotel choices.",
        client=_FailingFeedbackClient(),
    )

    assert result["submitted"] is False
    assert result["reason"] == "langsmith_error"
