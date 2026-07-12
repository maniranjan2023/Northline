"""
CI eval suite — guardrails, prompt injection, router intent.

Run:
  pytest evals/test_ci.py -v
  deepeval test run evals/test_ci.py -v

Results → evals/results/custom.md
"""

from __future__ import annotations

import os

import pytest

from chat_router import MessageIntent, classify_message
from evals.helpers.datasets import load_ci_goldens
from evals.reporting.write_results import record_custom_check
from guardrails.patterns import check_regex_safety
from guardrails.pipeline import check_input, guardrails_enabled

pytestmark = pytest.mark.ci

METRIC_GUARDRAIL = "Guardrail alignment"
METRIC_INJECTION = "Prompt injection block"
METRIC_ROUTER = "Router intent"


def _skip_guardrails_without_groq():
    if not guardrails_enabled():
        pytest.skip("GUARDRAILS_ENABLED=false")
    if not os.getenv("GROQ_API_KEY", "").strip():
        pytest.skip("GROQ_API_KEY not set — full guardrail checks skipped")


@pytest.mark.parametrize("case", load_ci_goldens()["guardrails"], ids=lambda c: c["id"])
def test_guardrail_alignment(case):
    """
    WHY: Travel queries must pass; harmful content must be blocked before agents run.
    HOW: NeMo Guardrails check_input() — same path as Streamlit frontend.
    """
    case_id = case["id"]
    user_input = case["input"]
    expect_blocked = case["expect_blocked"]

    # Regex-only harmful cases work without Groq; allow-list cases need full pipeline.
    if not expect_blocked:
        _skip_guardrails_without_groq()

    if expect_blocked and not os.getenv("GROQ_API_KEY", "").strip():
        regex_blocked, _, intent = check_regex_safety(user_input)
        if not regex_blocked:
            pytest.skip("GROQ_API_KEY not set and regex did not block this case")

    result = check_input(user_input)
    passed = result.blocked == expect_blocked
    reason = (
        f"blocked={result.blocked}, intent={result.intent}, expect_blocked={expect_blocked}"
    )
    if not passed and result.response:
        reason += f" | response={result.response[:200]}"

    record_custom_check(
        "custom",
        metric_name=METRIC_GUARDRAIL,
        case_id=case_id,
        passed=passed,
        reason=reason,
        input_preview=user_input,
    )
    assert passed, reason


@pytest.mark.parametrize("case", load_ci_goldens()["injection"], ids=lambda c: c["id"])
def test_prompt_injection_block(case):
    """
    WHY: Prompt injection must never reach LangGraph agents.
    HOW: Regex fast-path + NeMo input guardrails (check_input).
    """
    case_id = case["id"]
    user_input = case["input"]

    regex_blocked, regex_response, regex_intent = check_regex_safety(user_input)
    if regex_blocked:
        passed = case["expect_blocked"] is True
        reason = f"regex blocked: intent={regex_intent}"
        record_custom_check(
            "custom",
            metric_name=METRIC_INJECTION,
            case_id=case_id,
            passed=passed,
            reason=reason,
            input_preview=user_input,
        )
        assert passed, reason
        return

    _skip_guardrails_without_groq()
    result = check_input(user_input)
    passed = result.blocked == case["expect_blocked"]
    reason = f"blocked={result.blocked}, intent={result.intent}"
    record_custom_check(
        "custom",
        metric_name=METRIC_INJECTION,
        case_id=case_id,
        passed=passed,
        reason=reason,
        input_preview=user_input,
    )
    assert passed, reason


@pytest.mark.parametrize("case", load_ci_goldens()["router"], ids=lambda c: c["id"])
def test_router_intent(case):
    """
    WHY: Wrong routing wastes 6 agents or skips planning when user wants a new trip.
    HOW: classify_message() — deterministic, no LLM, same as frontend chat_router.
    """
    case_id = case["id"]
    user_input = case["input"]
    has_plan = case.get("has_previous_plan", False)
    expected = MessageIntent(case["expect_intent"])

    actual = classify_message(user_input, has_plan)
    passed = actual == expected
    reason = f"actual={actual.value}, expected={expected.value}"

    record_custom_check(
        "custom",
        metric_name=METRIC_ROUTER,
        case_id=case_id,
        passed=passed,
        reason=reason,
        input_preview=user_input,
    )
    assert passed, reason
