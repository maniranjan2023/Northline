"""Postgres-backed eval job + results store (shared by web API and worker)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_pool = None


def bind_pool(pool) -> None:
    """Bind the shared ConnectionPool (web init or worker startup)."""
    global _pool
    _pool = pool


def get_pool():
    global _pool
    if _pool is not None:
        return _pool
    # Reuse FastAPI app pool only if resources are already initialized
    # (do not trigger full graph/DB bootstrap from a capabilities probe).
    try:
        from app.dependencies import app_resources_ready, get_db_pool

        if app_resources_ready():
            _pool = get_db_pool()
            return _pool
    except Exception:
        pass
    raise RuntimeError("Eval job store has no DB pool. Call bind_pool() or init app resources.")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_job(row: dict[str, Any]) -> dict[str, Any]:
    progress = row.get("progress") or {}
    if isinstance(progress, str):
        progress = json.loads(progress)

    def _iso(value):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    return {
        "job_id": row["job_id"],
        "suite": row["suite"],
        "status": row["status"],
        "source": row.get("source") or "inngest",
        "inngest_run_id": row.get("inngest_run_id"),
        "progress": progress,
        "log_tail": row.get("log_tail") or "",
        "error": row.get("error"),
        "created_at": _iso(row.get("created_at")),
        "started_at": _iso(row.get("started_at")),
        "finished_at": _iso(row.get("finished_at")),
    }


def get_active_job_id() -> str | None:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id FROM eval_jobs
                WHERE status IN ('queued', 'running')
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            return row[0] if not isinstance(row, dict) else row["job_id"]


def create_job(
    *,
    job_id: str,
    suite: str,
    progress: dict[str, Any],
    source: str = "inngest",
    inngest_run_id: str | None = None,
) -> dict[str, Any]:
    pool = get_pool()
    now = _utc_now()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id FROM eval_jobs
                WHERE status IN ('queued', 'running')
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            existing = cur.fetchone()
            if existing:
                existing_id = existing[0] if not isinstance(existing, dict) else existing["job_id"]
                raise RuntimeError(f"Eval job {existing_id} is already running.")

            cur.execute(
                """
                INSERT INTO eval_jobs (
                    job_id, suite, status, source, inngest_run_id, progress,
                    log_tail, error, created_at, updated_at
                ) VALUES (%s, %s, 'queued', %s, %s, %s::jsonb, '', NULL, %s, %s)
                """,
                (
                    job_id,
                    suite,
                    source,
                    inngest_run_id,
                    json.dumps(progress),
                    now,
                    now,
                ),
            )
    return get_job(job_id) or {
        "job_id": job_id,
        "suite": suite,
        "status": "queued",
        "source": source,
        "progress": progress,
        "log_tail": "",
        "error": None,
        "created_at": now.isoformat(),
        "started_at": None,
        "finished_at": None,
    }


def get_job(job_id: str) -> dict[str, Any] | None:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id, suite, status, source, inngest_run_id, progress,
                       log_tail, error, created_at, started_at, finished_at
                FROM eval_jobs WHERE job_id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            if isinstance(row, dict):
                return _row_to_job(row)
            cols = [
                "job_id",
                "suite",
                "status",
                "source",
                "inngest_run_id",
                "progress",
                "log_tail",
                "error",
                "created_at",
                "started_at",
                "finished_at",
            ]
            return _row_to_job(dict(zip(cols, row)))


def list_jobs(limit: int = 10) -> list[dict[str, Any]]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id, suite, status, source, inngest_run_id, progress,
                       log_tail, error, created_at, started_at, finished_at
                FROM eval_jobs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    cols = [
        "job_id",
        "suite",
        "status",
        "source",
        "inngest_run_id",
        "progress",
        "log_tail",
        "error",
        "created_at",
        "started_at",
        "finished_at",
    ]
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(_row_to_job(row))
        else:
            out.append(_row_to_job(dict(zip(cols, row))))
    return out


def update_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    if not fields:
        return get_job(job_id)

    allowed = {
        "status",
        "source",
        "inngest_run_id",
        "progress",
        "log_tail",
        "error",
        "started_at",
        "finished_at",
    }
    sets: list[str] = []
    values: list[Any] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "progress":
            sets.append("progress = %s::jsonb")
            values.append(json.dumps(value))
        else:
            sets.append(f"{key} = %s")
            values.append(value)
    sets.append("updated_at = %s")
    values.append(_utc_now())
    values.append(job_id)

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE eval_jobs SET {', '.join(sets)} WHERE job_id = %s",
                values,
            )
    return get_job(job_id)


def append_log(job_id: str, text: str, max_chars: int = 8000) -> None:
    job = get_job(job_id)
    if not job:
        return
    combined = (job.get("log_tail") or "") + text
    update_job(job_id, log_tail=combined[-max_chars:])


def upsert_suite_results(suite: str, payload: dict[str, Any]) -> None:
    pool = get_pool()
    run_at = payload.get("run_at") or _utc_now().isoformat()
    now = _utc_now()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eval_suite_results (suite, payload, run_at, updated_at)
                VALUES (%s, %s::jsonb, %s, %s)
                ON CONFLICT (suite) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    run_at = EXCLUDED.run_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (suite, json.dumps(payload), run_at, now),
            )


def get_suite_results(suite: str) -> dict[str, Any] | None:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM eval_suite_results WHERE suite = %s",
                (suite,),
            )
            row = cur.fetchone()
            if not row:
                return None
            payload = row[0] if not isinstance(row, dict) else row["payload"]
            if isinstance(payload, str):
                return json.loads(payload)
            return dict(payload)


def get_all_suite_results() -> dict[str, dict[str, Any] | None]:
    return {
        "ci": get_suite_results("ci"),
        "single_turn": get_suite_results("single_turn"),
        "multi_turn": get_suite_results("multi_turn"),
    }
