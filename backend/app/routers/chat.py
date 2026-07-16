"""Chat routes."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies import get_lesson_book, get_memory_manager, get_travel_graph
from app.schemas.chat import ChatRequest, ChatResponse, PlanResponse, SessionRequest, SessionResponse
from app.services.chat_service import create_session, get_plan, handle_chat_message, stream_travel_graph
from lessons.service import LessonBookService
from memory.memory_manager import MemoryManager

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/session", response_model=SessionResponse)
async def start_session(
    payload: SessionRequest,
    memory_manager: MemoryManager = Depends(get_memory_manager),
) -> SessionResponse:
    session = await asyncio.to_thread(create_session, payload.username, memory_manager)
    return SessionResponse(**session)


@router.get("/plan", response_model=PlanResponse)
async def fetch_plan(
    username: str,
    thread_id: str,
    travel_graph=Depends(get_travel_graph),
    memory_manager: MemoryManager = Depends(get_memory_manager),
) -> PlanResponse:
    plan = await asyncio.to_thread(get_plan, username, thread_id, travel_graph, memory_manager)
    return PlanResponse(plan=plan)


@router.post("/message", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest,
    travel_graph=Depends(get_travel_graph),
    memory_manager: MemoryManager = Depends(get_memory_manager),
    lesson_book: LessonBookService = Depends(get_lesson_book),
) -> ChatResponse:
    result = await handle_chat_message(
        username=payload.username,
        thread_id=payload.thread_id,
        message=payload.message,
        travel_graph=travel_graph,
        memory_manager=memory_manager,
        lesson_book=lesson_book,
        run_id=payload.run_id,
    )
    return ChatResponse(
        intent=result["intent"],
        message=result.get("message", ""),
        run_id=result.get("run_id"),
        message_type=result.get("message_type", "text"),
        agents=result.get("agents"),
        guardrail_reason=result.get("guardrail_reason"),
        memory_update=result.get("memory_update"),
    )


@router.get("/stream")
async def stream_plan(
    username: str,
    thread_id: str,
    message: str,
    run_id: UUID,
    travel_graph=Depends(get_travel_graph),
    memory_manager: MemoryManager = Depends(get_memory_manager),
) -> StreamingResponse:
    if not message.strip():
        raise HTTPException(400, "Message is required.")
    safe_user = memory_manager.sanitize_user_id(username)
    generator = stream_travel_graph(
        user_query=message.strip(),
        username=safe_user,
        thread_id=thread_id,
        run_id=run_id,
        travel_graph=travel_graph,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
