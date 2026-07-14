"""Admin routes for lessons, proposals, and audit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_lesson_book, get_memory_manager, require_admin
from app.schemas.admin import (
    CandidateSummary,
    ImprovementEvent,
    LessonSummary,
    ProposalDetail,
    ProposalReviewRequest,
    ProposalSummary,
    SystemStatus,
)
from app.schemas.eval import (
    EvalCapabilities,
    EvalJobResponse,
    EvalResultsResponse,
    EvalRunRequest,
    EvalRunStartResponse,
    EvalSuiteResults,
)
from app.services.admin_service import (
    get_proposal,
    get_system_status,
    list_candidates,
    list_improvement_events,
    list_lessons,
    list_proposals,
    review_proposal,
)
from app.services.eval_runner_service import (
    get_capabilities,
    get_job,
    get_results_payload,
    list_recent_jobs,
    start_eval_job,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/status", response_model=SystemStatus)
def admin_status(memory_manager=Depends(get_memory_manager)) -> SystemStatus:
    return SystemStatus(**get_system_status(memory_manager))


@router.get("/proposals", response_model=list[ProposalSummary])
def proposals() -> list[ProposalSummary]:
    return [ProposalSummary(**item) for item in list_proposals()]


@router.get("/proposals/{proposal_id}", response_model=ProposalDetail)
def proposal_detail(proposal_id: str) -> ProposalDetail:
    detail = get_proposal(proposal_id)
    if not detail:
        raise HTTPException(404, "Proposal not found.")
    return ProposalDetail(**{k: v for k, v in detail.items() if k != "path"}, proposal=detail["proposal"])


@router.post("/proposals/{proposal_id}/review")
def proposal_review(proposal_id: str, payload: ProposalReviewRequest) -> dict:
    try:
        return review_proposal(
            proposal_id,
            action=payload.action,
            target_dataset=payload.target_dataset,
            reviewer_note=payload.reviewer_note,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/lessons", response_model=list[LessonSummary])
def lessons(active_only: bool = False, lesson_book=Depends(get_lesson_book)) -> list[LessonSummary]:
    return [LessonSummary(**item) for item in list_lessons(lesson_book, active_only=active_only)]


@router.get("/candidates", response_model=list[CandidateSummary])
def candidates(lesson_book=Depends(get_lesson_book)) -> list[CandidateSummary]:
    return [CandidateSummary(**item) for item in list_candidates(lesson_book)]


@router.get("/events", response_model=list[ImprovementEvent])
def events(limit: int = 100, lesson_book=Depends(get_lesson_book)) -> list[ImprovementEvent]:
    return [ImprovementEvent(**item) for item in list_improvement_events(lesson_book, limit=limit)]


def _optional_suite_results(data: dict | None) -> EvalSuiteResults | None:
    if not data:
        return None
    return EvalSuiteResults(**data)


@router.get("/evals/capabilities", response_model=EvalCapabilities)
def eval_capabilities() -> EvalCapabilities:
    return EvalCapabilities(**get_capabilities())


@router.get("/evals/results", response_model=EvalResultsResponse)
def eval_results() -> EvalResultsResponse:
    payload = get_results_payload()
    return EvalResultsResponse(
        ci=_optional_suite_results(payload.get("ci")),
        single_turn=_optional_suite_results(payload.get("single_turn")),
        multi_turn=_optional_suite_results(payload.get("multi_turn")),
        eval_deps_installed=payload.get("eval_deps_installed", False),
        active_job_id=payload.get("active_job_id"),
    )


@router.post("/evals/run", response_model=EvalRunStartResponse)
def eval_run(payload: EvalRunRequest) -> EvalRunStartResponse:
    try:
        result = start_eval_job(payload.suite)
        return EvalRunStartResponse(**result)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/evals/jobs", response_model=list[EvalJobResponse])
def eval_jobs(limit: int = 10) -> list[EvalJobResponse]:
    return [EvalJobResponse(**job) for job in list_recent_jobs(limit=limit)]


@router.get("/evals/jobs/{job_id}", response_model=EvalJobResponse)
def eval_job_status(job_id: str) -> EvalJobResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Eval job not found.")
    return EvalJobResponse(**job)
