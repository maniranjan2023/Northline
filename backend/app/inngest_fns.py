"""Inngest functions: manual eval triggers + daily cron schedules.

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

import inngest

from app.inngest_client import inngest_client
from app.services.eval_runner_service import execute_eval_job_blocking

# IST = Asia/Kolkata (user timezone)
CRON_CI = "TZ=Asia/Kolkata 0 12 * * *"
CRON_SINGLE_TURN = "TZ=Asia/Kolkata 0 18 * * *"
CRON_MULTI_TURN = "TZ=Asia/Kolkata 0 22 * * *"


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
    ctx.logger.info("Starting CI eval suite (job_id=%s)", ctx.run_id)

    def _run() -> dict:
        return execute_eval_job_blocking("ci", source="inngest", external_id=ctx.run_id)

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
    ctx.logger.info("Starting single-turn eval suite (job_id=%s)", ctx.run_id)

    def _run() -> dict:
        return execute_eval_job_blocking("single_turn", source="inngest", external_id=ctx.run_id)

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
    ctx.logger.info("Starting multi-turn eval suite (job_id=%s)", ctx.run_id)

    def _run() -> dict:
        return execute_eval_job_blocking("multi_turn", source="inngest", external_id=ctx.run_id)

    return await ctx.step.run("run-multi-turn-suite", _run)


@inngest_client.create_function(
    fn_id="evals-all",
    name="All 13 evals — manual only",
    trigger=inngest.TriggerEvent(event="evals/all.run"),
    retries=1,
)
async def evals_all(ctx: inngest.Context) -> dict:
    """Run CI → single-turn → multi-turn as separate durable steps."""
    ctx.logger.info("Starting full eval suite (job_id=%s)", ctx.run_id)

    def _run_ci() -> dict:
        return execute_eval_job_blocking("ci", source="inngest", external_id=f"{ctx.run_id}-ci")

    def _run_single() -> dict:
        return execute_eval_job_blocking(
            "single_turn", source="inngest", external_id=f"{ctx.run_id}-single"
        )

    def _run_multi() -> dict:
        return execute_eval_job_blocking(
            "multi_turn", source="inngest", external_id=f"{ctx.run_id}-multi"
        )

    ci = await ctx.step.run("run-ci", _run_ci)
    single = await ctx.step.run("run-single-turn", _run_single)
    multi = await ctx.step.run("run-multi-turn", _run_multi)
    return {"ci": ci, "single_turn": single, "multi_turn": multi}


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
