"""
Memory eval suite — DeepEval multi-turn conversation metrics.

Metrics (official DeepEval docs):
  - Knowledge Retention
  - Turn Relevancy
  - Turn Faithfulness        (needs retrieval_context on turns)
  - Turn Contextual Recall   (needs retrieval_context + expected_outcome)
  - Goal Accuracy

Run (live graph + MCP + Mem0 for session cases):
  set EVAL_LIVE=1
  deepeval test run evals/test_memory.py --verbose

Results → evals/results/multi_turn.md
"""

from __future__ import annotations

import os
import time

import pytest
from deepeval.test_case import ConversationalTestCase, Turn

from evals.helpers.datasets import load_memory_goldens
from evals.helpers.graph_runner import (
    _unique_eval_ids,
    build_retrieval_context,
    run_trip_planning,
)
from evals.helpers.judge import get_eval_judge
from evals.helpers.metrics import build_memory_metrics
from evals.reporting.write_results import record_deepeval_metric
from main import answer_follow_up

pytestmark = [pytest.mark.memory, pytest.mark.live]


def _require_live(live_eval_enabled: bool):
    if not live_eval_enabled:
        pytest.skip("Set EVAL_LIVE=1 to run memory evals.")
    if not os.getenv("GROQ_API_KEY", "").strip():
        pytest.skip("GROQ_API_KEY required.")


def _run_memory_metrics(
    convo: ConversationalTestCase,
    case_id: str,
    input_preview: str,
    judge,
) -> None:
    for name, metric in build_memory_metrics(judge):
        metric.measure(convo)
        record_deepeval_metric(
            "multi_turn",
            metric_name=name,
            case_id=case_id,
            score=metric.score,
            threshold=metric.threshold,
            reason=metric.reason or "",
            input_preview=input_preview,
        )
        assert metric.score >= metric.threshold, f"{name}: {metric.reason}"


def _build_checkpoint_followup_case(golden: dict) -> ConversationalTestCase:
    case_id = golden["id"]
    run1 = run_trip_planning(golden["turn1_input"], case_id=f"{case_id}_t1")
    plan = run1["plan"]
    retrieval = build_retrieval_context(plan, memory_snippet=" ".join(golden.get("retrieval_context_hints", [])))

    reply = answer_follow_up(
        golden["turn2_input"],
        username=run1["user_id"],
        chat_history=[
            {"role": "user", "content": golden["turn1_input"]},
            {"role": "assistant", "content": run1["itinerary"][:1500]},
        ],
        last_plan=plan,
        session_id=run1["thread_id"],
    )

    return ConversationalTestCase(
        turns=[
            Turn(role="user", content=golden["turn1_input"]),
            Turn(role="assistant", content=run1["itinerary"][:2000], retrieval_context=retrieval),
            Turn(role="user", content=golden["turn2_input"]),
            Turn(role="assistant", content=reply, retrieval_context=retrieval),
        ],
        expected_outcome=golden.get("expected_outcome", ""),
    )


def _build_memory_session_case(golden: dict) -> ConversationalTestCase:
    """Two graph runs with the same user_id so Mem0 can recall session-1 prefs."""
    from app.dependencies import get_memory_manager, init_app_resources

    init_app_resources()
    memory_manager = get_memory_manager()

    case_id = golden["id"]
    user_id, thread1 = _unique_eval_ids(f"{case_id}_mem")
    user_id = memory_manager.sanitize_user_id(user_id)
    thread2 = memory_manager.build_thread_id(f"{user_id}_s2")

    run1 = run_trip_planning(
        golden["session1_input"],
        case_id=f"{case_id}_s1",
        user_id=user_id,
        thread_id=thread1,
    )

    wait_s = int(golden.get("mem0_wait_seconds", 15))
    if os.getenv("MEM0_ENABLED", "true").lower() in {"1", "true", "yes"}:
        time.sleep(wait_s)

    run2 = run_trip_planning(
        golden["session2_input"],
        case_id=f"{case_id}_s2",
        user_id=user_id,
        thread_id=thread2,
    )

    retrieval = build_retrieval_context(
        run2["plan"],
        memory_snippet=" ".join(golden.get("retrieval_context_hints", [])),
    )

    return ConversationalTestCase(
        turns=[
            Turn(role="user", content=golden["session1_input"]),
            Turn(
                role="assistant",
                content=run1["itinerary"][:2000],
                retrieval_context=build_retrieval_context(run1["plan"]),
            ),
            Turn(role="user", content=golden["session2_input"]),
            Turn(role="assistant", content=run2["itinerary"][:2000], retrieval_context=retrieval),
        ],
        expected_outcome=golden.get("expected_outcome", ""),
    )


def _build_multi_turn_chat_case(golden: dict) -> ConversationalTestCase:
    """Multi-turn script: if the last turn is user, append a live graph assistant reply."""
    case_id = golden["id"]
    turns_spec = golden["turns"]
    turns: list[Turn] = []

    for spec in turns_spec:
        if spec["role"] == "user":
            turns.append(Turn(role="user", content=spec["content"]))
        else:
            turns.append(Turn(role="assistant", content=spec["content"]))

    if turns_spec and turns_spec[-1]["role"] == "user":
        run = run_trip_planning(turns_spec[-1]["content"], case_id=case_id)
        turns.append(
            Turn(
                role="assistant",
                content=run["itinerary"][:2000],
                retrieval_context=build_retrieval_context(run["plan"]),
            )
        )

    return ConversationalTestCase(
        turns=turns,
        expected_outcome=golden.get("expected_outcome", ""),
    )


@pytest.mark.parametrize("golden", load_memory_goldens(), ids=lambda g: g["id"])
def test_memory_multi_turn_metrics(golden, live_eval_enabled):
    """
    WHY: Follow-ups and Mem0 must preserve user prefs and plan context across turns.
    HOW: Build ConversationalTestCase from real graph + answer_follow_up runs.
    """
    _require_live(live_eval_enabled)
    judge = get_eval_judge()
    case_id = golden["id"]
    case_type = golden.get("type", "checkpoint_followup")

    if case_type == "checkpoint_followup":
        convo = _build_checkpoint_followup_case(golden)
        preview = golden.get("turn2_input", "")
    elif case_type == "memory_session":
        if not os.getenv("MEM0_API_KEY", "").strip():
            pytest.skip("MEM0_API_KEY required for memory_session cases.")
        convo = _build_memory_session_case(golden)
        preview = golden.get("session2_input", "")
    elif case_type == "multi_turn_chat":
        convo = _build_multi_turn_chat_case(golden)
        preview = golden["turns"][-1]["content"]
    else:
        pytest.skip(f"Unknown memory case type: {case_type}")

    _run_memory_metrics(convo, case_id, preview, judge)
