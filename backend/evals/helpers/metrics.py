"""Build DeepEval metrics using the shared Groq judge."""

from __future__ import annotations

import os

from deepeval.metrics import (
    ArgumentCorrectnessMetric,
    GoalAccuracyMetric,
    KnowledgeRetentionMetric,
    PlanAdherenceMetric,
    PlanQualityMetric,
    TaskCompletionMetric,
    ToolCorrectnessMetric,
    TurnContextualRecallMetric,
    TurnFaithfulnessMetric,
    TurnRelevancyMetric,
)
from deepeval.models import DeepEvalBaseLLM


def nightly_threshold() -> float:
    return float(os.getenv("EVAL_THRESHOLD", "0.7"))


def memory_threshold() -> float:
    return float(os.getenv("EVAL_THRESHOLD", "0.5"))


def build_trace_metrics(judge: DeepEvalBaseLLM, threshold: float | None = None):
    t = threshold if threshold is not None else nightly_threshold()
    return [
        TaskCompletionMetric(threshold=t, model=judge, include_reason=True),
        PlanAdherenceMetric(threshold=t, model=judge, include_reason=True),
        PlanQualityMetric(threshold=t, model=judge, include_reason=True),
    ]


def build_tool_correctness_metric(judge: DeepEvalBaseLLM, threshold: float | None = None):
    t = threshold if threshold is not None else nightly_threshold()
    return ToolCorrectnessMetric(threshold=t, model=judge, include_reason=True)


def build_argument_correctness_metric(judge: DeepEvalBaseLLM, threshold: float | None = None):
    t = threshold if threshold is not None else nightly_threshold()
    return ArgumentCorrectnessMetric(threshold=t, model=judge, include_reason=True)


def build_memory_metrics(judge: DeepEvalBaseLLM, threshold: float | None = None):
    t = threshold if threshold is not None else memory_threshold()
    return [
        ("KnowledgeRetentionMetric", KnowledgeRetentionMetric(threshold=t, model=judge, include_reason=True)),
        ("TurnRelevancyMetric", TurnRelevancyMetric(threshold=t, model=judge, include_reason=True)),
        ("TurnFaithfulnessMetric", TurnFaithfulnessMetric(threshold=t, model=judge, include_reason=True)),
        ("TurnContextualRecallMetric", TurnContextualRecallMetric(threshold=t, model=judge, include_reason=True)),
        ("GoalAccuracyMetric", GoalAccuracyMetric(threshold=t, model=judge, include_reason=True)),
    ]
