"""Warm MCP tool connections when the API starts."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_mcp_ready = False


def mcp_ready() -> bool:
    return _mcp_ready


async def warm_mcp_tools() -> None:
    """Initialize Tavily, AviationStack, and weather MCP tools on startup."""
    global _mcp_ready
    try:
        from mcp_client import initialize_mcp

        await initialize_mcp()
        _mcp_ready = True
        logger.info("MCP tools ready (Tavily, AviationStack, Weather).")
    except Exception as exc:
        _mcp_ready = False
        logger.warning("MCP warmup failed — tools will retry on first trip plan: %s", exc)
