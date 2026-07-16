"""Inngest functions: manual eval triggers + daily cron schedules.

Executed on the web service when Inngest invokes /api/inngest (official FastAPI serve).

Schedules (Asia/Kolkata):
  - CI (3 metrics)          → 12:00 every day
  - Single-turn (5 metrics) → 18:00 every day
  - Multi-turn (5 metrics)  → 22:00 every day

Manual triggers (Admin UI / API):
  - evals/ci.run
  - evals/single_turn.run
  - evals/multi_turn.run
  - evals/all.run
"""

from __future__ import annotations

from typing import Any

import inngest

from app.inngest_client import inngest_client
from app.services.eval_runner_service import execute_eval_job_blocking

CRON_CI = "TZ=Asia/Kolkata 0 12 * * *"
CRON_SINGLE_TURN = "TZ=Asia/Kolkata 0 18 * * *"
CRON_MULTI_TURN = "TZ=Asia/Kolkata 0 22 * * *"


def _event_job_id(ctx: inngest.Context) -> str | None:
    data = getattr(ctx.event, "data", None) or {}
    if isinstance(data, dict):
        value = data.get("job_id")
        return str(value) if value else None
    return None


def _run_suite(suite: str, ctx: inngest.Context) -> dict[str, Any]:
    return execute_eval_job_blocking(
        suite,  # type: ignore[arg-type]
        job_id=_event_job_id(ctx),
        source="inngest",
        inngest_run_id=str(ctx.run_id),
    )


@inngest_client.create_function(
    fn_id="evals-ci",
    name="CI evals — daily 12:00 IST + manual",
    trigger=[
        inngest.TriggerEvent(event="evals/ci.run"),
        inngest.TriggerCron(cron=CRON_CI),
    ],
    retries=1,
)
async def evals_ci(ctx: inngest.Context) -> dict:
    ctx.logger.info("Starting CI eval suite (run_id=%s)", ctx.run_id)

    def _run() -> dict:
        return _run_suite("ci", ctx)

    return await ctx.step.run("run-ci-suite", _run)


@inngest_client.create_function(
    fn_id="evals-single-turn",
    name="Single-turn evals — daily 18:00 IST + manual",
    trigger=[
        inngest.TriggerEvent(event="evals/single_turn.run"),
        inngest.TriggerCron(cron=CRON_SINGLE_TURN),
    ],
    retries=1,
)
async def evals_single_turn(ctx: inngest.Context) -> dict:
    ctx.logger.info("Starting single-turn eval suite (run_id=%s)", ctx.run_id)

    def _run() -> dict:
        return _run_suite("single_turn", ctx)

    return await ctx.step.run("run-single-turn-suite", _run)


@inngest_client.create_function(
    fn_id="evals-multi-turn",
    name="Multi-turn evals — daily 22:00 IST + manual",
    trigger=[
        inngest.TriggerEvent(event="evals/multi_turn.run"),
        inngest.TriggerCron(cron=CRON_MULTI_TURN),
    ],
    retries=1,
)
async def evals_multi_turn(ctx: inngest.Context) -> dict:
    ctx.logger.info("Starting multi-turn eval suite (run_id=%s)", ctx.run_id)

    def _run() -> dict:
        return _run_suite("multi_turn", ctx)

    return await ctx.step.run("run-multi-turn-suite", _run)


@inngest_client.create_function(
    fn_id="evals-all",
    name="All 13 evals — manual only",
    trigger=inngest.TriggerEvent(event="evals/all.run"),
    retries=1,
)
async def evals_all(ctx: inngest.Context) -> dict:
    """Run CI → single-turn → multi-turn as one job with durable steps."""
    ctx.logger.info("Starting full eval suite (run_id=%s)", ctx.run_id)
    job_id = _event_job_id(ctx)

    def _run() -> dict:
        return execute_eval_job_blocking(
            "all",
            job_id=job_id,
            source="inngest",
            inngest_run_id=str(ctx.run_id),
        )

    return await ctx.step.run("run-all-suites", _run)


INNGEST_FUNCTIONS = [
    evals_ci,
    evals_single_turn,
    evals_multi_turn,
    evals_all,
]

EVENT_BY_SUITE = {
    "ci": "evals/ci.run",
    "single_turn": "evals/single_turn.run",
    "multi_turn": "evals/multi_turn.run",
    "all": "evals/all.run",
}
