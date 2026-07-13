"""
Nightly eval suite — DeepEval single-turn / agent metrics.

Metrics (official DeepEval docs):
  - Task Completion      → requires @observe tracing
  - Plan Adherence       → requires @observe tracing
  - Plan Quality         → requires @observe tracing
  - Tool Correctness     → LLMTestCase + expected_tools
  - Argument Correctness → LLMTestCase + tools_called

Run (live graph + MCP required):
  set EVAL_LIVE=1
  deepeval test run evals/test_nightly.py --verbose

Results → evals/results/single_turn.md
"""

from __future__ import annotations

import os

import pytest
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import LLMTestCase, ToolCall
from deepeval.tracing import observe, update_current_trace

from evals.helpers.datasets import load_nightly_goldens
from evals.helpers.graph_runner import extract_tool_calls, run_trip_planning
from evals.helpers.judge import get_eval_judge
from evals.helpers.metrics import (
    build_argument_correctness_metric,
    build_tool_correctness_metric,
    build_trace_metrics,
)
from evals.reporting.write_results import record_deepeval_metric

pytestmark = [pytest.mark.nightly, pytest.mark.live]


def _require_live(live_eval_enabled: bool):
    if not live_eval_enabled:
        pytest.skip("Set EVAL_LIVE=1 to run nightly graph evals (MCP + DB + APIs).")
    if not os.getenv("GROQ_API_KEY", "").strip():
        pytest.skip("GROQ_API_KEY required for judge and graph.")
    if not os.getenv("DATABASE_URL", "").strip():
        pytest.skip("DATABASE_URL required for LangGraph checkpointer.")


def _expected_tool_calls(names: list[str]) -> list[ToolCall]:
    return [ToolCall(name=n) for n in names]


@pytest.mark.parametrize("golden", load_nightly_goldens(), ids=lambda g: g["id"])
def test_nightly_single_turn_metrics(golden, live_eval_enabled):
    """
    WHY: One-shot trip planning must complete with correct tools and a coherent plan.
    HOW: Run full LangGraph inside DeepEval @observe trace; measure all 5 metrics.
    """
    _require_live(live_eval_enabled)
    judge = get_eval_judge()
    case_id = golden["id"]
    user_input = golden["input"]
    captured: dict = {}

    trace_metrics = build_trace_metrics(judge)
    tool_metric = build_tool_correctness_metric(judge)
    arg_metric = build_argument_correctness_metric(judge)

    @observe()
    def _run_observed(inp: str):
        run_result = run_trip_planning(inp, case_id=case_id)
        captured.update(run_result)
        tools = extract_tool_calls(run_result["state"])
        update_current_trace(
            input=inp,
            output=run_result.get("itinerary", ""),
            tools_called=tools,
        )
        return run_result.get("itinerary", "")

    dataset = EvaluationDataset(goldens=[Golden(input=user_input)])
    for _golden in dataset.evals_iterator(metrics=trace_metrics):
        _run_observed(_golden.input)

    for metric in trace_metrics:
        record_deepeval_metric(
            "single_turn",
            metric_name=metric.__class__.__name__,
            case_id=case_id,
            score=metric.score,
            threshold=metric.threshold,
            reason=metric.reason or "",
            input_preview=user_input,
        )
        assert metric.score >= metric.threshold, (
            f"{metric.__class__.__name__}: {metric.score} < {metric.threshold} — {metric.reason}"
        )

    tools_called = extract_tool_calls(captured["state"])
    test_case = LLMTestCase(
        input=user_input,
        actual_output=captured.get("itinerary", ""),
        tools_called=tools_called,
        expected_tools=_expected_tool_calls(golden.get("expected_tools", [])),
    )

    tool_metric.measure(test_case)
    record_deepeval_metric(
        "single_turn",
        metric_name="ToolCorrectnessMetric",
        case_id=case_id,
        score=tool_metric.score,
        threshold=tool_metric.threshold,
        reason=tool_metric.reason or "",
        input_preview=user_input,
    )
    assert tool_metric.score >= tool_metric.threshold, tool_metric.reason

    arg_test = LLMTestCase(
        input=user_input,
        actual_output=captured.get("itinerary", ""),
        tools_called=tools_called,
    )
    arg_metric.measure(arg_test)
    record_deepeval_metric(
        "single_turn",
        metric_name="ArgumentCorrectnessMetric",
        case_id=case_id,
        score=arg_metric.score,
        threshold=arg_metric.threshold,
        reason=arg_metric.reason or "",
        input_preview=user_input,
    )
    assert arg_metric.score >= arg_metric.threshold, arg_metric.reason
