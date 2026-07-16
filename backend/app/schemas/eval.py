"""Eval runner API schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


EvalSuiteRequest = Literal["all", "ci", "single_turn", "multi_turn"]
EvalSuiteKey = Literal["ci", "single_turn", "multi_turn"]
SuiteRunStatus = Literal["queued", "running", "completed", "failed", "skipped"]
JobStatus = Literal["queued", "running", "completed", "failed"]


class EvalRunRequest(BaseModel):
    suite: EvalSuiteRequest = "all"


class SuiteProgress(BaseModel):
    status: SuiteRunStatus = "queued"
    passed: int | None = None
    failed: int | None = None
    total: int | None = None
    exit_code: int | None = None
    duration_seconds: float | None = None
    error: str | None = None


class EvalJobResponse(BaseModel):
    job_id: str
    suite: EvalSuiteRequest
    status: JobStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    progress: dict[EvalSuiteKey, SuiteProgress] = Field(default_factory=dict)
    error: str | None = None
    log_tail: str = ""


class EvalMetricSummary(BaseModel):
    metric_name: str
    passed: int
    total: int
    pass_rate: float


class EvalResultRow(BaseModel):
    metric_name: str
    case_id: str
    passed: bool
    score: float | None = None
    threshold: float | None = None
    reason: str = ""
    input_preview: str = ""


class EvalSuiteResults(BaseModel):
    suite: str
    suite_label: str
    run_at: str | None = None
    passed: int = 0
    total: int = 0
    metrics_summary: list[EvalMetricSummary] = Field(default_factory=list)
    rows: list[EvalResultRow] = Field(default_factory=list)


class EvalResultsResponse(BaseModel):
    ci: EvalSuiteResults | None = None
    single_turn: EvalSuiteResults | None = None
    multi_turn: EvalSuiteResults | None = None
    eval_deps_installed: bool = False
    inngest_configured: bool = False
    active_job_id: str | None = None
    schedules: dict[str, Any] = Field(default_factory=dict)


class EvalRunStartResponse(BaseModel):
    job_id: str
    suite: EvalSuiteRequest
    status: JobStatus
    message: str


class EvalCapabilities(BaseModel):
    eval_deps_installed: bool
    deepeval_available: bool
    pytest_available: bool
    inngest_configured: bool = False
    active_job_id: str | None = None
    schedules: dict[str, Any] = Field(default_factory=dict)
    suites: dict[str, Any] = Field(default_factory=dict)
