"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import env_loader  # noqa: F401
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS  # noqa: E402
from app.dependencies import init_app_resources, shutdown_app_resources  # noqa: E402
from app.routers import admin, chat, feedback, health  # noqa: E402
from mcp_bootstrap import warm_mcp_tools  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Bind port immediately; warm heavy resources and MCP in the background.
    init_task = asyncio.create_task(asyncio.to_thread(init_app_resources))
    warmup_task = asyncio.create_task(warm_mcp_tools())
    yield
    for task in (init_task, warmup_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await asyncio.to_thread(shutdown_app_resources)


app = FastAPI(
    title="Northline API",
    description="Travel planning backend with lesson book and self-improvement admin APIs.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

# Inngest serve — sync with Inngest Cloud at /api/inngest (official FastAPI pattern).
# Manual + cron eval jobs execute here when Inngest invokes the endpoint.
import inngest.fast_api  # noqa: E402
from app.inngest_client import inngest_client  # noqa: E402
from app.inngest_fns import INNGEST_FUNCTIONS  # noqa: E402

inngest.fast_api.serve(app, inngest_client, INNGEST_FUNCTIONS)
