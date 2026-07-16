"""Background eval job runner for Admin UI + Inngest."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.config import BACKEND_ROOT
from evals.reporting.write_results import load_all_latest_results, load_latest_suite_results

EvalSuiteRequest = Literal["all", "ci", "single_turn", "multi_turn"]
EvalSuiteKey = Literal["ci", "single_turn", "multi_turn"]

JOBS_DIR = BACKEND_ROOT / "evals" / "jobs"
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

# Daily schedules shown in Admin UI (Asia/Kolkata)
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

_lock = threading.Lock()
_active_job_id: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_jobs_dir() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _read_job(job_id: str) -> dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_job(job: dict[str, Any]) -> None:
    _ensure_jobs_dir()
    _job_path(job["job_id"]).write_text(json.dumps(job, indent=2), encoding="utf-8")


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def eval_deps_installed() -> bool:
    return _module_available("pytest") and _module_available("deepeval")


def get_capabilities() -> dict[str, Any]:
    from app.inngest_client import inngest_configured

    return {
        "eval_deps_installed": eval_deps_installed(),
        "deepeval_available": _module_available("deepeval"),
        "pytest_available": _module_available("pytest"),
        "inngest_configured": inngest_configured(),
        "active_job_id": _active_job_id,
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


def _empty_progress() -> dict[str, dict[str, Any]]:
    return {key: {"status": "queued"} for key in SUITE_ORDER}


def _suites_for_request(suite: EvalSuiteRequest) -> list[EvalSuiteKey]:
    if suite == "all":
        return list(SUITE_ORDER)
    return [suite]


def get_active_job_id() -> str | None:
    with _lock:
        return _active_job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    return _read_job(job_id)


def list_recent_jobs(limit: int = 10) -> list[dict[str, Any]]:
    _ensure_jobs_dir()
    jobs: list[dict[str, Any]] = []
    for path in sorted(JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
        if len(jobs) >= limit:
            break
    return jobs


def _create_job_record(
    suite: EvalSuiteRequest,
    *,
    source: str = "local",
    external_id: str | None = None,
) -> dict[str, Any]:
    global _active_job_id

    with _lock:
        if _active_job_id:
            existing = _read_job(_active_job_id)
            if existing and existing.get("status") in {"queued", "running"}:
                raise RuntimeError(f"Eval job {_active_job_id} is already running.")

        job_id = (external_id or uuid.uuid4().hex)[:24]
        suites = _suites_for_request(suite)
        progress = _empty_progress()
        for key in SUITE_ORDER:
            if key not in suites:
                progress[key]["status"] = "skipped"

        job = {
            "job_id": job_id,
            "suite": suite,
            "status": "queued",
            "source": source,
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "progress": progress,
            "error": None,
            "log_tail": "",
        }
        _write_job(job)
        _active_job_id = job_id
        return job


def start_eval_job(suite: EvalSuiteRequest = "all") -> dict[str, Any]:
    """Start evals via Inngest when configured, otherwise a local background thread."""
    if not eval_deps_installed():
        raise RuntimeError(
            "Eval dependencies not installed. Run: pip install -r requirements-evals.txt"
        )

    from app.inngest_client import inngest_configured

    if inngest_configured():
        return trigger_eval_via_inngest(suite)

    job = _create_job_record(suite, source="local")
    suites = _suites_for_request(suite)
    thread = threading.Thread(target=_run_job, args=(job["job_id"], suites), daemon=True)
    thread.start()

    return {
        "job_id": job["job_id"],
        "suite": suite,
        "status": "queued",
        "message": (
            f"Started local eval job for {suite}. "
            f"Poll /admin/evals/jobs/{job['job_id']} for progress."
        ),
    }


def trigger_eval_via_inngest(suite: EvalSuiteRequest = "all") -> dict[str, Any]:
    """Send an Inngest event so Cloud/Dev Server executes the matching function."""
    import inngest

    from app.inngest_client import inngest_client

    event_name = EVENT_BY_SUITE[suite]
    result = inngest_client.send_sync(
        inngest.Event(
            name=event_name,
            data={"suite": suite, "triggered_by": "admin"},
        )
    )
    ids = getattr(result, "ids", None) or []
    if getattr(result, "error", None):
        raise RuntimeError(f"Inngest send failed: {result.error}")
    event_id = ids[0] if ids else "queued"
    return {
        "job_id": str(event_id)[:24],
        "suite": suite,
        "status": "queued",
        "message": (
            f"Queued via Inngest ({event_name}). "
            "Track progress in the Inngest dashboard and refresh results here when done."
        ),
    }


def execute_eval_job_blocking(
    suite: EvalSuiteRequest,
    *,
    source: str = "inngest",
    external_id: str | None = None,
) -> dict[str, Any]:
    """Run evals synchronously (used inside Inngest step.run). Returns final job dict."""
    if not eval_deps_installed():
        raise RuntimeError(
            "Eval dependencies not installed. Install requirements-evals.txt on this server."
        )

    job = _create_job_record(suite, source=source, external_id=external_id)
    suites = _suites_for_request(suite)
    _run_job(job["job_id"], suites)
    final = _read_job(job["job_id"]) or job
    return {
        "job_id": final.get("job_id"),
        "suite": final.get("suite"),
        "status": final.get("status"),
        "progress": final.get("progress"),
        "error": final.get("error"),
        "finished_at": final.get("finished_at"),
    }


def _append_log(job: dict[str, Any], text: str, max_chars: int = 8000) -> None:
    combined = (job.get("log_tail") or "") + text
    job["log_tail"] = combined[-max_chars:]


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


def _apply_suite_results(job: dict[str, Any], suite_key: EvalSuiteKey) -> None:
    latest = load_latest_suite_results(suite_key)
    progress = job["progress"][suite_key]
    if latest:
        progress["passed"] = latest.get("passed", 0)
        progress["total"] = latest.get("total", 0)
        progress["failed"] = progress["total"] - progress["passed"]


def _run_job(job_id: str, suites: list[EvalSuiteKey]) -> None:
    global _active_job_id

    job = _read_job(job_id)
    if not job:
        return

    job["status"] = "running"
    job["started_at"] = _utc_now()
    _write_job(job)

    overall_failed = False

    for suite_key in suites:
        progress = job["progress"][suite_key]
        progress["status"] = "running"
        _write_job(job)

        started = time.monotonic()
        try:
            result = _run_subprocess(suite_key)
            duration = round(time.monotonic() - started, 2)
            progress["duration_seconds"] = duration
            progress["exit_code"] = result.returncode
            _append_log(job, f"\n--- {suite_key} ---\n")
            _append_log(job, result.stdout or "")
            _append_log(job, result.stderr or "")

            _apply_suite_results(job, suite_key)

            if result.returncode == 0:
                progress["status"] = "completed"
            else:
                progress["status"] = "failed"
                progress["error"] = (result.stderr or result.stdout or "Suite failed")[:500]
                overall_failed = True
        except subprocess.TimeoutExpired:
            progress["status"] = "failed"
            progress["error"] = "Suite timed out after 60 minutes."
            overall_failed = True
        except Exception as exc:  # noqa: BLE001
            progress["status"] = "failed"
            progress["error"] = str(exc)[:500]
            overall_failed = True

        _write_job(job)

    job["status"] = "failed" if overall_failed else "completed"
    job["finished_at"] = _utc_now()
    if overall_failed:
        job["error"] = "One or more eval suites failed. See progress and log for details."
    _write_job(job)

    with _lock:
        if _active_job_id == job_id:
            _active_job_id = None


def get_results_payload() -> dict[str, Any]:
    from app.inngest_client import inngest_configured

    raw = load_all_latest_results()
    payload: dict[str, Any] = {
        "eval_deps_installed": eval_deps_installed(),
        "inngest_configured": inngest_configured(),
        "active_job_id": get_active_job_id(),
        "schedules": SCHEDULES,
    }
    for key in SUITE_ORDER:
        data = raw.get(key)
        payload[key] = data
    return payload
