"""Run async coroutines safely from sync code (including inside FastAPI's event loop)."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="northline-async")


def shutdown_executor() -> None:
    _executor.shutdown(wait=False, cancel_futures=True)


def run_coroutine_sync(coro, *, timeout: float = 120):
    """Execute a coroutine from sync code without nesting asyncio.run on a live loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = _executor.submit(asyncio.run, coro)
    return future.result(timeout=timeout)
