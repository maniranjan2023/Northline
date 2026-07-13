"""Admin services for proposals, lessons, and audit events."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import GOLDEN_DATASETS, PROPOSED_DIR


def _proposal_review_path(proposal_path: Path) -> Path:
    return proposal_path.with_suffix(".review.json")


def _load_proposal_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _review_status(path: Path) -> str:
    review_path = _proposal_review_path(path)
    if review_path.exists():
        data = json.loads(review_path.read_text(encoding="utf-8"))
        return str(data.get("status", "pending"))
    return "pending"


def list_proposals() -> list[dict[str, Any]]:
    proposals = []
    if not PROPOSED_DIR.exists():
        return proposals
    for path in sorted(PROPOSED_DIR.glob("*.json"), reverse=True):
        if path.name.endswith(".review.json"):
            continue
        try:
            data = _load_proposal_file(path)
        except (json.JSONDecodeError, OSError):
            continue
        source = data.get("source", {})
        diagnosis = data.get("diagnosis", {})
        proposed = data.get("proposed_golden", {})
        proposals.append(
            {
                "id": path.stem,
                "filename": path.name,
                "run_id": source.get("run_id", ""),
                "component": diagnosis.get("component", "unknown"),
                "target_dataset": proposed.get("target_dataset", "nightly"),
                "feedback_comment": source.get("feedback_comment", ""),
                "review_status": _review_status(path),
                "created_at": source.get("created_at"),
            }
        )
    return proposals


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    path = PROPOSED_DIR / f"{proposal_id}.json"
    if not path.exists():
        matches = list(PROPOSED_DIR.glob(f"*{proposal_id}*.json"))
        path = matches[0] if matches else None
    if not path or not path.exists() or path.name.endswith(".review.json"):
        return None
    data = _load_proposal_file(path)
    summary = next((item for item in list_proposals() if item["filename"] == path.name), {})
    return {**summary, "proposal": data, "path": str(path)}


def review_proposal(
    proposal_id: str,
    *,
    action: str,
    target_dataset: str | None,
    reviewer_note: str,
) -> dict[str, Any]:
    detail = get_proposal(proposal_id)
    if not detail:
        raise FileNotFoundError(f"Proposal not found: {proposal_id}")
    path = Path(detail["path"])
    status = "rejected" if action == "reject" else "approved"
    review_record = {
        "status": status,
        "reviewer_note": reviewer_note,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "target_dataset": target_dataset,
    }
    _proposal_review_path(path).write_text(json.dumps(review_record, indent=2), encoding="utf-8")

    golden_path = None
    if action == "approve":
        dataset_key = target_dataset or detail.get("target_dataset", "nightly")
        golden_path = GOLDEN_DATASETS.get(dataset_key)
        if not golden_path:
            raise ValueError(f"Unknown dataset: {dataset_key}")
        proposal = detail["proposal"]
        case = proposal.get("proposed_golden", {}).get("case")
        if not case:
            raise ValueError("Proposal does not contain a golden case payload.")
        golden = json.loads(golden_path.read_text(encoding="utf-8")) if golden_path.exists() else {}
        section = case.get("section") or proposal["proposed_golden"].get("section")
        if section not in golden:
            golden[section] = []
        case_id = case.get("id") or f"approved_{proposal_id[:24]}"
        case["id"] = case_id
        case["review_status"] = "approved"
        case["approved_from_run_id"] = detail.get("run_id")
        golden[section] = [item for item in golden.get(section, []) if item.get("id") != case_id]
        golden[section].append(case)
        golden_path.write_text(json.dumps(golden, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        archive_dir = PROPOSED_DIR / "approved"
        archive_dir.mkdir(exist_ok=True)
        shutil.move(str(path), str(archive_dir / path.name))

    return {
        "proposal_id": proposal_id,
        "status": status,
        "golden_path": str(golden_path) if golden_path else None,
        "reviewer_note": reviewer_note,
    }


def lesson_to_dict(lesson) -> dict[str, Any]:
    return {
        "lesson_id": str(lesson.lesson_id),
        "lesson": lesson.lesson,
        "category": lesson.category,
        "confidence": lesson.confidence,
        "times_seen": lesson.times_seen,
        "status": lesson.status,
        "destination": lesson.destination,
        "evidence_count": len(lesson.evidence),
    }


def list_lessons(lesson_book, *, active_only: bool = False) -> list[dict[str, Any]]:
    lessons = lesson_book._repo.list_lessons(active_only=active_only)
    return [lesson_to_dict(lesson) for lesson in lessons]


def list_candidates(lesson_book) -> list[dict[str, Any]]:
    repo = lesson_book._repo
    if hasattr(repo, "_pool"):
        with repo._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT candidate_id, suggested_lesson, category, problem, times_seen, confidence, status
                    FROM candidate_lessons ORDER BY last_updated DESC LIMIT 100
                    """
                )
                rows = cur.fetchall()
        return [
            {
                "candidate_id": str(row[0]),
                "suggested_lesson": row[1],
                "category": row[2],
                "problem": row[3],
                "times_seen": int(row[4]),
                "confidence": float(row[5]),
                "status": row[6],
            }
            for row in rows
        ]
    return [
        {
            "candidate_id": str(candidate.candidate_id),
            "suggested_lesson": candidate.suggested_lesson,
            "category": candidate.category,
            "problem": candidate.problem,
            "times_seen": candidate.times_seen,
            "confidence": candidate.confidence,
            "status": candidate.status,
        }
        for candidate in getattr(repo, "candidates", {}).values()
    ]


def list_improvement_events(lesson_book, *, limit: int = 100) -> list[dict[str, Any]]:
    return lesson_book._repo.list_events(limit=limit)


def get_system_status(memory_manager) -> dict[str, Any]:
    from guardrails.flags import guardrails_enabled
    from observability import get_langsmith_status

    return {
        "guardrails_enabled": guardrails_enabled(),
        "mem0_enabled": memory_manager.config.mem0_enabled,
        "langsmith": get_langsmith_status(),
    }
