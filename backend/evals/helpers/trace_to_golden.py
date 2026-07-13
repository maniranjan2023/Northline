"""Convert negatively rated LangSmith traces into reviewable eval proposals."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from dotenv import load_dotenv
from langsmith import Client

PROPOSED_DIR = Path(__file__).resolve().parent.parent / "datasets" / "proposed"
KNOWN_TOOLS = {
    "tavily_search",
    "list_airports",
    "list_airlines",
    "get_current_weather",
    "get_forecast",
}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def _walk_runs(run: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield run
    for child in run.get("child_runs") or []:
        yield from _walk_runs(_as_dict(child))


def _text_from(value: Any, preferred_keys: tuple[str, ...]) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        messages = [_text_from(item, preferred_keys) for item in value]
        return "\n".join(item for item in messages if item)
    if isinstance(value, dict):
        for key in preferred_keys:
            text = _text_from(value.get(key), preferred_keys)
            if text:
                return text
    return ""


def _input_text(trace: dict[str, Any]) -> str:
    return _text_from(
        trace.get("inputs"),
        ("user_query", "input", "messages", "prompt", "content", "text"),
    )


def _output_text(trace: dict[str, Any]) -> str:
    return _text_from(
        trace.get("outputs"),
        ("itinerary", "output", "generations", "message", "content", "text", "messages"),
    )


def _redact_text(text: str, *, limit: int = 5000) -> str:
    """Remove common PII/secrets before proposals reach disk or CI artifacts."""
    value = text or ""
    value = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[REDACTED_EMAIL]",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"(?<!\w)(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){9,12}(?!\w)",
        "[REDACTED_PHONE]",
        value,
    )
    value = re.sub(
        r"\b(?:sk-|key-|token-)[A-Za-z0-9_-]{16,}\b",
        "[REDACTED_SECRET]",
        value,
        flags=re.IGNORECASE,
    )
    return value[:limit]


def _metadata(trace: dict[str, Any]) -> dict[str, Any]:
    extra = trace.get("extra") or {}
    return trace.get("metadata") or extra.get("metadata") or {}


def _tool_calls(trace: dict[str, Any]) -> list[str]:
    tools: list[str] = []
    for run in _walk_runs(trace):
        name = str(run.get("name") or "").strip()
        if name in KNOWN_TOOLS and name not in tools:
            tools.append(name)
    return tools


def _slug(text: str, limit: int = 36) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return value[:limit].rstrip("_") or "feedback_case"


def diagnose_failure(trace: dict[str, Any], comment: str) -> dict[str, Any]:
    """Suggest the component to inspect using trace evidence and user wording."""
    trace = _as_dict(trace)
    comment_lower = comment.lower()
    input_text = _redact_text(_input_text(trace))
    evidence = [f"User feedback: {_redact_text(comment.strip(), limit=500)}"]
    child_errors = [
        str(run.get("name"))
        for run in _walk_runs(trace)
        if run.get("error")
    ]

    if child_errors:
        component = child_errors[0]
        failure_type = "runtime_error"
        evidence.append(f"Trace error in {component}")
    elif any(word in comment_lower for word in ("forgot", "remember", "preference", "vegetarian", "vegan", "halal")):
        component, failure_type = "memory_retrieval", "missing_user_context"
    elif any(word in comment_lower for word in ("flight", "airport", "airline")):
        component, failure_type = "flight_agent", "missing_tool_or_result"
    elif any(word in comment_lower for word in ("hotel", "stay", "room")):
        component, failure_type = "hotel_agent", "missing_tool_or_result"
    elif any(word in comment_lower for word in ("weather", "forecast", "activity")):
        component, failure_type = "activity_agent", "missing_tool_or_result"
    elif any(word in comment_lower for word in ("unsafe", "pii", "blocked", "jailbreak")):
        component, failure_type = "guardrails.pipeline", "safety_misclassification"
    elif any(word in comment_lower for word in ("route", "greeting", "wrong intent")):
        component, failure_type = "chat_router", "wrong_intent"
    elif any(word in comment_lower for word in ("budget", "days", "destination")):
        component, failure_type = "planner_agent", "constraint_missed"
    else:
        component, failure_type = "final_response_agent", "low_response_quality"

    observed_tools = _tool_calls(trace)
    if observed_tools:
        evidence.append(f"Observed tools: {', '.join(observed_tools)}")
    if input_text:
        evidence.append(f"Input: {input_text[:180]}")

    checks = {
        "flight_agent": ["list_airports", "list_airlines", "flight_results"],
        "hotel_agent": ["tavily_search", "hotel_results"],
        "activity_agent": ["get_current_weather", "get_forecast", "activity_results"],
        "memory_retrieval": ["retrieve_memory", "memory_context", "Mem0 user_id"],
        "guardrails.pipeline": ["input decision", "output decision", "matched rule"],
        "chat_router": ["classified intent", "has_previous_plan"],
        "planner_agent": ["planner constraints", "final itinerary"],
        "final_response_agent": ["agent outputs", "itinerary completeness"],
    }
    return {
        "component": component,
        "failure_type": failure_type,
        "confidence": 0.9 if child_errors else 0.75,
        "evidence": evidence,
        "suggested_checks": checks.get(component, [component]),
    }


def _expected_tools(input_text: str, observed: list[str]) -> list[str]:
    tools = list(observed)
    text = input_text.lower()

    def add(name: str) -> None:
        if name not in tools:
            tools.append(name)

    if any(word in text for word in ("hotel", "activity", "research", "things to do")):
        add("tavily_search")
    if any(word in text for word in ("flight", "airport", "airline", " from ")):
        add("list_airports")
        add("list_airlines")
    if any(word in text for word in ("weather", "forecast")):
        add("get_current_weather")
        add("get_forecast")
    return tools


def build_proposal(trace: dict[str, Any], *, comment: str, score: int = 0) -> dict[str, Any]:
    """Build a draft envelope; approved golden datasets are never changed here."""
    trace = _as_dict(trace)
    run_id = str(trace.get("id") or trace.get("run_id") or "")
    input_text = _redact_text(_input_text(trace))
    output_text = _redact_text(_output_text(trace))
    clean_comment = _redact_text(comment.strip(), limit=1000)
    tags = list(trace.get("tags") or [])
    diagnosis = diagnose_failure(trace, comment)
    case_id = f"feedback_{_slug(input_text)}_{run_id[:8]}"
    is_follow_up = "follow-up" in tags or diagnosis["component"] == "memory_retrieval"

    if is_follow_up:
        target_dataset = "golden_memory.json"
        proposed_golden = {
            "id": case_id,
            "type": "multi_turn_chat",
            "turns": [
                {"role": "user", "content": input_text},
                {"role": "assistant", "content": output_text},
            ],
            "expected_outcome": f"Correct the reported issue: {clean_comment}",
            "note": f"Proposed from negatively rated LangSmith run {run_id}",
        }
    elif diagnosis["component"] in {"guardrails.pipeline", "chat_router"}:
        target_dataset = "golden_ci.json"
        if diagnosis["component"] == "chat_router":
            proposed_golden = {
                "section": "router",
                "case": {
                    "id": case_id,
                    "input": input_text,
                    "expect_intent": "REVIEW_REQUIRED",
                    "has_previous_plan": False,
                    "note": clean_comment,
                },
            }
        else:
            proposed_golden = {
                "section": "guardrails",
                "case": {
                    "id": case_id,
                    "input": input_text,
                    "expect_blocked": "REVIEW_REQUIRED",
                    "note": clean_comment,
                },
            }
    else:
        target_dataset = "golden_nightly.json"
        proposed_golden = {
            "id": case_id,
            "input": input_text,
            "expected_tools": _expected_tools(input_text, _tool_calls(trace)),
            "task_hint": f"Correct the reported issue: {clean_comment}",
        }

    return {
        "schema_version": 1,
        "review_status": "draft",
        "target_dataset": target_dataset,
        "source": {
            "type": "langsmith_trace",
            "run_id": run_id,
            "run_name": str(trace.get("name") or ""),
            "project": _metadata(trace).get("project")
            or os.getenv("LANGSMITH_PROJECT", "northline-travel"),
            "feedback_score": score,
            "feedback_comment": clean_comment,
            "output_preview": output_text[:500],
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "diagnosis": diagnosis,
        "proposed_golden": proposed_golden,
    }


def write_proposal(proposal: dict[str, Any], output_dir: Path = PROPOSED_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = proposal["source"]["run_id"][:8] or "unknown"
    component = _slug(proposal["diagnosis"]["component"], 24)
    path = output_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{component}_{run_id}.json"
    counter = 2
    while path.exists():
        path = output_dir / f"{path.stem}_{counter}.json"
        counter += 1
    path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def proposal_from_run(
    run_id: str | UUID,
    *,
    comment: str,
    score: int = 0,
    client: Any | None = None,
    output_dir: Path = PROPOSED_DIR,
) -> tuple[dict[str, Any], Path]:
    load_dotenv(override=True)
    langsmith_client = client or Client()
    run = langsmith_client.read_run(run_id, load_child_runs=True)
    proposal = build_proposal(_as_dict(run), comment=comment, score=score)
    return proposal, write_proposal(proposal, output_dir)


def collect_negative_feedback(
    *,
    client: Any | None = None,
    limit: int = 50,
    output_dir: Path = PROPOSED_DIR,
    project: str | None = None,
) -> list[Path]:
    """Collect negatively rated runs; skip run IDs already proposed."""
    load_dotenv(override=True)
    langsmith_client = client or Client()
    project_name = project or os.getenv("LANGSMITH_PROJECT", "northline-travel")
    existing_run_ids = set()
    for path in output_dir.glob("*.json") if output_dir.exists() else []:
        try:
            existing_run_ids.add(json.loads(path.read_text(encoding="utf-8"))["source"]["run_id"])
        except (KeyError, json.JSONDecodeError):
            continue

    paths = []
    feedback_items = langsmith_client.list_feedback(
        feedback_key=["user_rating"],
        limit=limit,
    )
    for feedback in feedback_items:
        item = _as_dict(feedback)
        if item.get("score") != 0 or not item.get("run_id"):
            continue
        run_id = str(item["run_id"])
        if run_id in existing_run_ids:
            continue
        project_runs = list(
            langsmith_client.list_runs(
                project_name=project_name,
                run_ids=[run_id],
                is_root=True,
                limit=1,
            )
        )
        if not project_runs:
            continue
        _, path = proposal_from_run(
            run_id,
            comment=str(item.get("comment") or "Negative user feedback"),
            score=0,
            client=langsmith_client,
            output_dir=output_dir,
        )
        paths.append(path)
        existing_run_ids.add(run_id)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-id")
    mode.add_argument("--collect-negative", action="store_true")
    parser.add_argument("--comment", default="Negative user feedback")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--project", default=os.getenv("LANGSMITH_PROJECT", "northline-travel"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.collect_negative:
        paths = collect_negative_feedback(limit=args.limit, project=args.project)
        print(f"Created {len(paths)} proposal(s).")
        for path in paths:
            print(path)
        return 0

    load_dotenv(override=True)
    run = Client().read_run(args.run_id, load_child_runs=True)
    proposal = build_proposal(_as_dict(run), comment=args.comment, score=0)
    if args.dry_run:
        print(json.dumps(proposal, indent=2, ensure_ascii=False))
    else:
        print(write_proposal(proposal))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
