"""Load golden datasets from evals/datasets/*.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"


def _load_json(name: str) -> Any:
    path = DATASETS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_ci_goldens() -> dict[str, list[dict[str, Any]]]:
    """CI golden: guardrails, injection, router sections."""
    return _load_json("golden_ci.json")


def load_nightly_goldens() -> list[dict[str, Any]]:
    """Nightly golden: single-turn trip planning cases."""
    return _load_json("golden_nightly.json")


def load_memory_goldens() -> list[dict[str, Any]]:
    """Memory golden: multi-turn conversation cases."""
    return _load_json("golden_memory.json")
