"""
Append structured eval results to suite-specific Markdown files.

Each suite writes to its own file under evals/results/:
  - custom.md       (CI: guardrails, injection, router)
  - single_turn.md  (nightly DeepEval agent metrics)
  - multi_turn.md   (weekly DeepEval conversation metrics)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

SuiteName = Literal["custom", "single_turn", "multi_turn"]

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

SUITE_FILES: dict[SuiteName, str] = {
    "custom": "custom.md",
    "single_turn": "single_turn.md",
    "multi_turn": "multi_turn.md",
}

SUITE_LABELS: dict[SuiteName, str] = {
    "custom": "CI (custom)",
    "single_turn": "Nightly (single-turn)",
    "multi_turn": "Memory (multi-turn)",
}


@dataclass
class EvalRow:
    """One metric result for a single test case."""

    metric_name: str
    case_id: str
    passed: bool
    score: float | None = None
    threshold: float | None = None
    reason: str = ""
    input_preview: str = ""


@dataclass
class ResultsCollector:
    """Thread-safe collector; flushed to Markdown at end of pytest session."""

    suite: SuiteName
    rows: list[EvalRow] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(
        self,
        *,
        metric_name: str,
        case_id: str,
        passed: bool,
        score: float | None = None,
        threshold: float | None = None,
        reason: str = "",
        input_preview: str = "",
    ) -> None:
        with self._lock:
            self.rows.append(
                EvalRow(
                    metric_name=metric_name,
                    case_id=case_id,
                    passed=passed,
                    score=score,
                    threshold=threshold,
                    reason=(reason or "").strip(),
                    input_preview=(input_preview or "")[:120],
                )
            )

    def flush(self) -> Path | None:
        with self._lock:
            if not self.rows:
                return None
            return append_results_md(self.suite, self.rows)


_collectors: dict[SuiteName, ResultsCollector] = {}
_collectors_lock = threading.Lock()


def get_collector(suite: SuiteName) -> ResultsCollector:
    with _collectors_lock:
        if suite not in _collectors:
            _collectors[suite] = ResultsCollector(suite=suite)
        return _collectors[suite]


def flush_all_collectors() -> list[Path]:
    written: list[Path] = []
    with _collectors_lock:
        for collector in _collectors.values():
            path = collector.flush()
            if path:
                written.append(path)
    return written


def _now_local_str() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _init_md_if_missing(path: Path, suite: SuiteName) -> None:
    if path.exists():
        return
    label = SUITE_LABELS[suite]
    path.write_text(
        f"# Voyager AI — {label} Eval Results\n\n"
        "This file is **append-only**. Each run adds a dated section below.\n\n"
        "| Column | Meaning |\n"
        "|--------|--------|\n"
        "| **Eval Metric** | Metric or check name |\n"
        "| **Case** | Golden dataset case id |\n"
        "| **Result** | PASS or FAIL |\n"
        "| **Score** | DeepEval score (custom checks use —) |\n"
        "| **Threshold** | Minimum passing score |\n"
        "| **Reason** | Judge explanation or assert message |\n\n"
        "---\n\n",
        encoding="utf-8",
    )


def append_results_md(suite: SuiteName, rows: list[EvalRow]) -> Path:
    """Append one run block to the suite Markdown file."""
    _ensure_results_dir()
    path = RESULTS_DIR / SUITE_FILES[suite]
    _init_md_if_missing(path, suite)

    passed = sum(1 for r in rows if r.passed)
    total = len(rows)
    timestamp = _now_local_str()

    lines = [
        f"## Run: {timestamp} | Suite: {SUITE_LABELS[suite]} | Pass: {passed}/{total}\n",
        "| Eval Metric | Case | Result | Score | Threshold | Reason |",
        "|-------------|------|--------|-------|-----------|--------|",
    ]

    for row in rows:
        score_s = f"{row.score:.2f}" if row.score is not None else "—"
        thresh_s = f"{row.threshold:.2f}" if row.threshold is not None else "—"
        reason = row.reason.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {row.metric_name} | {row.case_id} | "
            f"{'PASS' if row.passed else 'FAIL'} | {score_s} | {thresh_s} | {reason} |"
        )

    lines.append("\n---\n\n")

    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    return path


def record_deepeval_metric(
    suite: SuiteName,
    *,
    metric_name: str,
    case_id: str,
    score: float,
    threshold: float,
    reason: str,
    input_preview: str = "",
) -> None:
    """Helper for DeepEval metrics after measure()."""
    get_collector(suite).add(
        metric_name=metric_name,
        case_id=case_id,
        passed=score >= threshold,
        score=score,
        threshold=threshold,
        reason=reason,
        input_preview=input_preview,
    )


def record_custom_check(
    suite: SuiteName,
    *,
    metric_name: str,
    case_id: str,
    passed: bool,
    reason: str,
    input_preview: str = "",
) -> None:
    """Helper for deterministic CI checks (guardrails, router)."""
    get_collector(suite).add(
        metric_name=metric_name,
        case_id=case_id,
        passed=passed,
        reason=reason,
        input_preview=input_preview,
    )
