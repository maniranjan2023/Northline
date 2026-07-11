import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

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

    # Neon requires SSL for remote connections.
    query.setdefault("sslmode", "require")

    # channel_binding=require often breaks psycopg pools on Windows.
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


def setup_memory_schema(pool: ConnectionPool) -> None:
    """
    Create long-term memory tables and pgvector extension.

    Safe to run multiple times because SQL uses IF NOT EXISTS.
    """
    migration_path = os.path.join(
        os.path.dirname(__file__),
        "migrations",
        "001_memory_tables.sql",
    )

    with open(migration_path, "r", encoding="utf-8") as file:
        sql = file.read()

    # Execute each SQL statement separately for clearer errors.
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    with pool.connection() as conn:
        for statement in statements:
            conn.execute(statement + ";")


def create_checkpointer() -> tuple[PostgresSaver, ConnectionPool]:
    """Create a pooled Postgres checkpointer for Neon."""
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

    # Prepare long-term memory tables in the same Neon database.
    try:
        setup_memory_schema(pool)
    except Exception as exc:
        print(f"Memory schema setup warning: {exc}")

    return checkpointer, pool
