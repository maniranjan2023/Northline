"""Database configuration — PostgresSaver for LangGraph short-term memory."""

import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

load_dotenv(override=True)


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
        kwargs={"autocommit": True, "prepare_threshold": 0},
        timeout=60,
    )
    pool.open(wait=True, timeout=60)

    checkpointer = PostgresSaver(pool)
    checkpointer.setup()

    return checkpointer, pool
