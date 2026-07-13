"""Backend configuration."""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
PROPOSED_DIR = BACKEND_ROOT / "evals" / "datasets" / "proposed"
GOLDEN_DATASETS = {
    "ci": BACKEND_ROOT / "evals" / "datasets" / "golden_ci.json",
    "nightly": BACKEND_ROOT / "evals" / "datasets" / "golden_nightly.json",
    "memory": BACKEND_ROOT / "evals" / "datasets" / "golden_memory.json",
}

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "dev-admin-key")
