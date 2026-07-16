"""Shared FastAPI dependencies and app singletons (lazy-loaded)."""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import Header, HTTPException, status

from app.config import ADMIN_API_KEY  # noqa: E402

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_resources: dict[str, Any] | None = None


def app_resources_ready() -> bool:
    return _resources is not None


def init_app_resources() -> None:
    """Load graph, DB checkpointer, memory, and lesson book (slow — run once)."""
    global _resources
    with _lock:
        if _resources is not None:
            return

        from db_config import create_checkpointer
        from graph.builder import build_travel_graph
        from langchain_groq import ChatGroq
        from lessons.service import LessonBookService
        from memory.memory_manager import MemoryManager
        from observability import configure_langsmith

        logger.info("Initializing Northline resources (graph, Postgres, memory)...")
        configure_langsmith()

        llm = ChatGroq(model="llama-3.3-70b-versatile")
        checkpointer, db_pool = create_checkpointer()
        memory_manager = MemoryManager(llm=llm)
        lesson_book = LessonBookService.from_pool(db_pool)
        travel_graph = build_travel_graph(llm, memory_manager, checkpointer, lesson_book)

        try:
            from app.services.eval_job_store import bind_pool

            bind_pool(db_pool)
        except Exception as exc:
            logger.warning("Eval job store bind failed: %s", exc)

        _resources = {
            "llm": llm,
            "checkpointer": checkpointer,
            "db_pool": db_pool,
            "memory_manager": memory_manager,
            "lesson_book": lesson_book,
            "travel_graph": travel_graph,
        }
        logger.info("Northline resources ready.")


def shutdown_app_resources() -> None:
    """Release DB pool and other singletons on API shutdown."""
    global _resources
    with _lock:
        if _resources is None:
            return
        from async_utils import shutdown_executor
        from db_config import close_pool

        close_pool(_resources.get("db_pool"))
        shutdown_executor()
        _resources = None
        logger.info("Northline resources shut down.")


def _require(name: str) -> Any:
    init_app_resources()
    assert _resources is not None
    return _resources[name]


def get_llm():
    return _require("llm")


def get_checkpointer():
    return _require("checkpointer")


def get_db_pool():
    return _require("db_pool")


def get_memory_manager():
    return _require("memory_manager")


def get_lesson_book():
    return _require("lesson_book")


def get_travel_graph():
    return _require("travel_graph")


def __getattr__(name: str) -> Any:
    """Backward-compatible lazy access for `from app.dependencies import travel_graph`."""
    if name in {"llm", "checkpointer", "db_pool", "memory_manager", "lesson_book", "travel_graph"}:
        return _require(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def require_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    if not ADMIN_API_KEY:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Admin API is not configured.")
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid admin key.")
