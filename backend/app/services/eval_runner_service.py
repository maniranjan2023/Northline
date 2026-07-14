"""Background eval job runner for Admin UI."""

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
    return {
        "eval_deps_installed": eval_deps_installed(),
        "deepeval_available": _module_available("deepeval"),
        "pytest_available": _module_available("pytest"),
        "active_job_id": _active_job_id,
        "suites": {
            key: {
                "label": SUITE_LABELS[key],
                "metric_count": METRIC_COUNTS[key],
                "requires_live": key != "ci",
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


def start_eval_job(suite: EvalSuiteRequest = "all") -> dict[str, Any]:
    global _active_job_id

    if not eval_deps_installed():
        raise RuntimeError(
            "Eval dependencies not installed. Run: pip install -r requirements-dev.txt"
        )

    with _lock:
        if _active_job_id:
            existing = _read_job(_active_job_id)
            if existing and existing.get("status") in {"queued", "running"}:
                raise RuntimeError(f"Eval job {_active_job_id} is already running.")

        job_id = uuid.uuid4().hex[:12]
        suites = _suites_for_request(suite)
        progress = _empty_progress()
        for key in SUITE_ORDER:
            if key not in suites:
                progress[key]["status"] = "skipped"

        job = {
            "job_id": job_id,
            "suite": suite,
            "status": "queued",
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "progress": progress,
            "error": None,
            "log_tail": "",
        }
        _write_job(job)
        _active_job_id = job_id

    thread = threading.Thread(target=_run_job, args=(job_id, suites), daemon=True)
    thread.start()

    return {
        "job_id": job_id,
        "suite": suite,
        "status": "queued",
        "message": f"Started eval job for {suite}. Poll /admin/evals/jobs/{job_id} for progress.",
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
    raw = load_all_latest_results()
    payload: dict[str, Any] = {
        "eval_deps_installed": eval_deps_installed(),
        "active_job_id": get_active_job_id(),
    }
    for key in SUITE_ORDER:
        data = raw.get(key)
        payload[key] = data
    return payload
