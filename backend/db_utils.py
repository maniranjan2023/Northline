"""Postgres helpers — retries for transient Neon/SSL disconnects."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_TRANSIENT_MARKERS = (
    "ssl error",
    "unexpected eof",
    "connection",
    "timeout",
    "broken pipe",
    "closed",
    "consuming input failed",
    "server closed",
)


def is_transient_db_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _TRANSIENT_MARKERS)


def with_db_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    delay_s: float = 0.4,
) -> T:
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if attempt + 1 >= attempts or not is_transient_db_error(exc):
                raise
            logger.warning("Transient DB error (retry %d/%d): %s", attempt + 1, attempts, exc)
            time.sleep(delay_s * (attempt + 1))
    assert last is not None
    raise last
