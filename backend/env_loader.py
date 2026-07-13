"""Load backend environment variables from backend/.env."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_ROOT.parent


def load_app_env() -> None:
    """Load backend/.env; fall back to repo-root .env only for unset keys."""
    load_dotenv(BACKEND_ROOT / ".env", override=True)
    load_dotenv(REPO_ROOT / ".env", override=False)


load_app_env()
