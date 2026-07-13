"""Database configuration — PostgresSaver for LangGraph short-term memory."""

import logging
import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import env_loader  # noqa: F401 — loads backend/.env
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


def normalize_neon_database_url(url: str) -> str:
    """Normalize a Neon/Postgres URL for psycopg3 + LangGraph."""
    if not url:
        raise ValueError(
            "DATABASE_URL is not set. Add your Neon connection string to .env"
        )

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")

    if query.get("channel_binding") == "require":
        query["channel_binding"] = "prefer"

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query),
            parsed.fragment,
        )
    )


def create_checkpointer() -> tuple[PostgresSaver, ConnectionPool]:
    """
    Create PostgresSaver for LangGraph short-term memory.

    Checkpoints are keyed by thread_id and saved after every node.
    Raises if Postgres is unavailable — short-term memory is required.
    """
    database_url = normalize_neon_database_url(os.getenv("DATABASE_URL", ""))

    pool = ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=10,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "connect_timeout": 30,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
        timeout=60,
        max_lifetime=300,
        max_idle=120,
        reconnect_timeout=60,
        check=ConnectionPool.check_connection,
    )
    pool.open(wait=True, timeout=60)

    checkpointer = PostgresSaver(pool)
    checkpointer.setup()

    try:
        from lessons.schema import setup_lesson_schema

        setup_lesson_schema(pool)
    except Exception as exc:
        raise RuntimeError(f"Lesson book schema setup failed: {exc}") from exc

    return checkpointer, pool


def close_pool(pool: ConnectionPool | None) -> None:
    """Close the Postgres pool cleanly on shutdown."""
    if pool is None:
        return
    try:
        pool.close()
        logger.info("Postgres connection pool closed.")
    except Exception as exc:
        logger.warning("Postgres pool close failed: %s", exc)
