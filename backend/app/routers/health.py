"""Health and status routes."""

from fastapi import APIRouter, Depends

from app.dependencies import app_resources_ready, get_memory_manager
from app.services.admin_service import get_system_status
from mcp_bootstrap import mcp_ready
from memory.memory_manager import MemoryManager

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "mcp_ready": mcp_ready(),
        "resources_ready": app_resources_ready(),
    }


@router.get("/status")
def status(memory_manager: MemoryManager = Depends(get_memory_manager)) -> dict:
    payload = get_system_status(memory_manager)
    payload["mcp_ready"] = mcp_ready()
    payload["resources_ready"] = True
    return payload
