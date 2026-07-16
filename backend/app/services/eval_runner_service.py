"""Eval job enqueue + execute via Inngest serve on the web service."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Literal

from app.config import BACKEND_ROOT
from evals.reporting.write_results import load_all_latest_results, load_latest_suite_results

EvalSuiteRequest = Literal["all", "ci", "single_turn", "multi_turn"]
EvalSuiteKey = Literal["ci", "single_turn", "multi_turn"]

SUITE_ORDER: list[EvalSuiteKey] = ["ci", "single_turn", "multi_turn"]

SUITE_COMMANDS: dict[EvalSuiteKey, list[str]] = {
    "ci": ["-m", "pytest", "evals/test_ci.py", "-q"],
    "single_turn": ["-m", "pytest", "evals/test_nightly.py", "-q"],
    "multi_turn": ["-m", "pytest", "evals/test_memory.py", "-q"],
}

SUITE_LABELS: dict[EvalSuiteKey, str] = {
    "ci": "CI (3 custom checks)",
    "single_turn": "Single-turn (5 DeepEval metrics)",
    "multi_turn": "Multi-turn (5 DeepEval metrics)",
}

METRIC_COUNTS: dict[EvalSuiteKey, int] = {
    "ci": 3,
    "single_turn": 5,
    "multi_turn": 5,
}

SCHEDULES: dict[EvalSuiteKey, dict[str, str]] = {
    "ci": {"cron": "0 12 * * *", "label": "Every day at 12:00 IST", "timezone": "Asia/Kolkata"},
    "single_turn": {
        "cron": "0 18 * * *",
        "label": "Every day at 18:00 IST",
        "timezone": "Asia/Kolkata",
    },
    "multi_turn": {
        "cron": "0 22 * * *",
        "label": "Every day at 22:00 IST",
        "timezone": "Asia/Kolkata",
    },
}

EVENT_BY_SUITE: dict[EvalSuiteRequest, str] = {
    "ci": "evals/ci.run",
    "single_turn": "evals/single_turn.run",
    "multi_turn": "evals/multi_turn.run",
    "all": "evals/all.run",
}

def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def eval_deps_installed() -> bool:
    return _module_available("pytest") and _module_available("deepeval")


def _empty_progress(suite: EvalSuiteRequest) -> dict[str, dict[str, Any]]:
    suites = _suites_for_request(suite)
    progress = {key: {"status": "queued"} for key in SUITE_ORDER}
    for key in SUITE_ORDER:
        if key not in suites:
            progress[key]["status"] = "skipped"
    return progress


def _suites_for_request(suite: EvalSuiteRequest) -> list[EvalSuiteKey]:
    if suite == "all":
        return list(SUITE_ORDER)
    return [suite]


def get_capabilities() -> dict[str, Any]:
    from app.inngest_client import inngest_configured
    from app.services import eval_job_store as store

    active = None
    try:
        active = store.get_active_job_id()
    except Exception:
        active = None

    return {
        "eval_deps_installed": eval_deps_installed(),
        "deepeval_available": _module_available("deepeval"),
        "pytest_available": _module_available("pytest"),
        "inngest_configured": inngest_configured(),
        "worker_mode": "inngest_serve",
        "active_job_id": active,
        "schedules": SCHEDULES,
        "suites": {
            key: {
                "label": SUITE_LABELS[key],
                "metric_count": METRIC_COUNTS[key],
                "requires_live": key != "ci",
                "schedule": SCHEDULES[key],
            }
            for key in SUITE_ORDER
        },
    }


def get_active_job_id() -> str | None:
    from app.services import eval_job_store as store

    try:
        return store.get_active_job_id()
    except Exception:
        return None


def get_job(job_id: str) -> dict[str, Any] | None:
    from app.services import eval_job_store as store

    try:
        return store.get_job(job_id)
    except Exception:
        return None


def list_recent_jobs(limit: int = 10) -> list[dict[str, Any]]:
    from app.services import eval_job_store as store

    try:
        return store.list_jobs(limit=limit)
    except Exception:
        return []


def start_eval_job(suite: EvalSuiteRequest = "all") -> dict[str, Any]:
    """Enqueue via Inngest (preferred) or local thread fallback when Inngest is unset."""
    from app.inngest_client import inngest_configured

    if inngest_configured():
        return enqueue_eval_via_inngest(suite)

    # Local-only fallback (no Connect worker): still requires eval deps on this process.
    if not eval_deps_installed():
        raise RuntimeError(
            "Eval dependencies not installed. Run: pip install -r requirements-evals.txt "
            "(and install requirements-evals.txt on this server)."
        )
    return _start_local_thread_job(suite)


def enqueue_eval_via_inngest(suite: EvalSuiteRequest = "all") -> dict[str, Any]:
    """Create a Postgres job row and send an Inngest event (executed via /api/inngest)."""
    import inngest

    from app.inngest_client import inngest_client
    from app.services import eval_job_store as store

    job_id = uuid.uuid4().hex[:16]
    progress = _empty_progress(suite)
    job = store.create_job(
        job_id=job_id,
        suite=suite,
        progress=progress,
        source="inngest",
    )

    event_name = EVENT_BY_SUITE[suite]
    result = inngest_client.send_sync(
        inngest.Event(
            name=event_name,
            data={
                "suite": suite,
                "job_id": job_id,
                "triggered_by": "admin",
            },
        )
    )
    if getattr(result, "error", None):
        store.update_job(job_id, status="failed", error=f"Inngest send failed: {result.error}")
        raise RuntimeError(f"Inngest send failed: {result.error}")

    return {
        "job_id": job_id,
        "suite": suite,
        "status": "queued",
        "message": (
            f"Queued via Inngest Connect ({event_name}). "
            f"Worker will process job {job_id}. Poll /admin/evals/jobs/{job_id}."
        ),
    }


def _start_local_thread_job(suite: EvalSuiteRequest) -> dict[str, Any]:
    from app.services import eval_job_store as store

    job_id = uuid.uuid4().hex[:16]
    progress = _empty_progress(suite)
    store.create_job(job_id=job_id, suite=suite, progress=progress, source="local")
    suites = _suites_for_request(suite)
    thread = threading.Thread(
        target=execute_eval_job_blocking,
        kwargs={"suite": suite, "job_id": job_id, "source": "local"},
        daemon=True,
    )
    thread.start()
    return {
        "job_id": job_id,
        "suite": suite,
        "status": "queued",
        "message": (
            f"Started local eval job for {suite} (Inngest not configured). "
            f"Poll /admin/evals/jobs/{job_id}."
        ),
    }


def execute_eval_job_blocking(
    suite: EvalSuiteRequest,
    *,
    job_id: str | None = None,
    source: str = "inngest",
    inngest_run_id: str | None = None,
) -> dict[str, Any]:
    """Run evals synchronously (Inngest step / local thread). Updates Postgres."""
    from app.services import eval_job_store as store

    if not eval_deps_installed():
        raise RuntimeError(
            "Eval dependencies not installed. Install requirements-evals.txt on this server."
        )

    if job_id:
        job = store.get_job(job_id)
        if not job:
            progress = _empty_progress(suite)
            job = store.create_job(
                job_id=job_id,
                suite=suite,
                progress=progress,
                source=source,
                inngest_run_id=inngest_run_id,
            )
        elif inngest_run_id:
            store.update_job(job_id, inngest_run_id=inngest_run_id)
    else:
        job_id = (inngest_run_id or uuid.uuid4().hex)[:24]
        progress = _empty_progress(suite)
        job = store.create_job(
            job_id=job_id,
            suite=suite,
            progress=progress,
            source=source,
            inngest_run_id=inngest_run_id,
        )

    suites = _suites_for_request(suite)
    _run_job(job_id, suites)
    final = store.get_job(job_id) or job
    return {
        "job_id": final.get("job_id"),
        "suite": final.get("suite"),
        "status": final.get("status"),
        "progress": final.get("progress"),
        "error": final.get("error"),
        "finished_at": final.get("finished_at"),
    }


def _run_subprocess(suite_key: EvalSuiteKey) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if suite_key != "ci":
        env["EVAL_LIVE"] = "1"
    cmd = [sys.executable, *SUITE_COMMANDS[suite_key]]
    return subprocess.run(
        cmd,
        cwd=str(BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=3600,
    )


def _persist_suite_results_to_db(suite_key: EvalSuiteKey) -> dict[str, Any] | None:
    from app.services import eval_job_store as store

    latest = load_latest_suite_results(suite_key)
    if not latest:
        return None
    # Normalize suite key for API/DB (`ci` not `custom`)
    payload = dict(latest)
    payload["suite"] = suite_key
    store.upsert_suite_results(suite_key, payload)
    return payload


def _run_job(job_id: str, suites: list[EvalSuiteKey]) -> None:
    from datetime import datetime, timezone

    from app.services import eval_job_store as store

    job = store.get_job(job_id)
    if not job:
        return

    now = datetime.now(timezone.utc)
    progress = dict(job.get("progress") or {})
    store.update_job(job_id, status="running", started_at=now, progress=progress)

    overall_failed = False
    log_tail = job.get("log_tail") or ""

    for suite_key in suites:
        progress[suite_key] = {**(progress.get(suite_key) or {}), "status": "running"}
        store.update_job(job_id, progress=progress)

        started = time.monotonic()
        try:
            result = _run_subprocess(suite_key)
            duration = round(time.monotonic() - started, 2)
            suite_progress = progress[suite_key]
            suite_progress["duration_seconds"] = duration
            suite_progress["exit_code"] = result.returncode
            log_tail = (log_tail + f"\n--- {suite_key} ---\n" + (result.stdout or "") + (result.stderr or ""))[
                -8000:
            ]

            latest = _persist_suite_results_to_db(suite_key)
            if latest:
                suite_progress["passed"] = latest.get("passed", 0)
                suite_progress["total"] = latest.get("total", 0)
                suite_progress["failed"] = suite_progress["total"] - suite_progress["passed"]

            if result.returncode == 0:
                suite_progress["status"] = "completed"
            else:
                suite_progress["status"] = "failed"
                suite_progress["error"] = (result.stderr or result.stdout or "Suite failed")[:500]
                overall_failed = True
        except subprocess.TimeoutExpired:
            progress[suite_key]["status"] = "failed"
            progress[suite_key]["error"] = "Suite timed out after 60 minutes."
            overall_failed = True
        except Exception as exc:  # noqa: BLE001
            progress[suite_key]["status"] = "failed"
            progress[suite_key]["error"] = str(exc)[:500]
            overall_failed = True

        store.update_job(job_id, progress=progress, log_tail=log_tail)

    finished = datetime.now(timezone.utc)
    store.update_job(
        job_id,
        status="failed" if overall_failed else "completed",
        finished_at=finished,
        error=(
            "One or more eval suites failed. See progress and log for details."
            if overall_failed
            else None
        ),
        progress=progress,
        log_tail=log_tail,
    )


def get_results_payload() -> dict[str, Any]:
    from app.inngest_client import inngest_configured
    from app.services import eval_job_store as store

    # Prefer Postgres (shared across web + worker); fall back to local JSON files.
    try:
        raw = store.get_all_suite_results()
    except Exception:
        raw = {}

    file_raw = load_all_latest_results()
    payload: dict[str, Any] = {
        "eval_deps_installed": eval_deps_installed(),
        "inngest_configured": inngest_configured(),
        "worker_mode": "inngest_serve",
        "active_job_id": get_active_job_id(),
        "schedules": SCHEDULES,
    }
    for key in SUITE_ORDER:
        payload[key] = raw.get(key) or file_raw.get(key)
    return payload
