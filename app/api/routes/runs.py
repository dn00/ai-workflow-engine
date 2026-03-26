"""Route handlers for /runs endpoints (spec §25)."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_event_repo,
    get_receipt_repo,
    get_run_repo,
    get_runner,
)
from app.api.schemas.runs import (
    CreateRunRequest,
    EventListResponse,
    EventResponse,
    ReplayResultResponse,
    RunResponse,
    RunResultResponse,
    SubmitReviewRequest,
)
from app.core.bundle import BundleError, assemble_bundle
from app.core.enums import ReviewDecision, RunMode
from app.core.models import Event, Run
from app.core.replay.models import ReplayResult
from app.core.runners.base import RunnerError
from app.core.runners.local_runner import LocalRunner
from app.core.runners.models import RunResult
from app.db.repositories.base import (
    AbstractEventRepository,
    AbstractReceiptRepository,
    AbstractRunRepository,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_run(run: Run) -> RunResponse:
    return RunResponse(**run.model_dump())


def _serialize_event(event: Event) -> EventResponse:
    data = event.model_dump()
    return EventResponse(**data)


def _serialize_run_result(result: RunResult) -> RunResultResponse:
    return RunResultResponse(
        run=_serialize_run(result.run),
        projection=result.projection.model_dump(),
        review_task=result.review_task.model_dump() if result.review_task else None,
    )


def _serialize_replay_result(result: ReplayResult) -> ReplayResultResponse:
    return ReplayResultResponse(
        run_id=result.run_id,
        replayed_projection=(
            result.replayed_projection.model_dump()
            if result.replayed_projection
            else None
        ),
        stored_projection=result.stored_projection,
        match=result.match,
        event_count=result.event_count,
        error=result.error,
    )


def _map_runner_error(exc: RunnerError) -> HTTPException:
    """Map RunnerError messages to appropriate HTTP status codes."""
    msg = str(exc)
    if "Run not found" in msg:
        return HTTPException(status_code=404, detail=msg)
    if "not in review_required status" in msg:
        return HTTPException(status_code=409, detail=msg)
    if "Cannot use REPLAY mode" in msg:
        return HTTPException(status_code=400, detail=msg)
    if "LLM proposal generation failed" in msg:
        return HTTPException(status_code=502, detail=msg)
    return HTTPException(status_code=500, detail=msg)


# ---------------------------------------------------------------------------
# Task 002: Run endpoints (POST, GET, events)
# ---------------------------------------------------------------------------


@router.post("/", response_model=RunResultResponse, status_code=201)
def create_run(
    body: CreateRunRequest,
    runner: LocalRunner = Depends(get_runner),
):
    try:
        mode = RunMode(body.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {body.mode}")
    try:
        result = runner.start_run(body.input_text, mode, workflow_type=body.workflow_type)
    except RunnerError as exc:
        raise _map_runner_error(exc)
    return _serialize_run_result(result)


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: str,
    run_repo: AbstractRunRepository = Depends(get_run_repo),
):
    run = run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return _serialize_run(run)


@router.get("/{run_id}/events", response_model=EventListResponse)
def get_run_events(
    run_id: str,
    run_repo: AbstractRunRepository = Depends(get_run_repo),
    event_repo: AbstractEventRepository = Depends(get_event_repo),
):
    # Verify run exists first
    run = run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    events = event_repo.list_by_run(run_id)
    return EventListResponse(
        run_id=run_id,
        events=[_serialize_event(e) for e in events],
    )


# ---------------------------------------------------------------------------
# Task 003: Review + Replay endpoints
# ---------------------------------------------------------------------------


@router.post("/{run_id}/review", response_model=RunResultResponse)
def submit_review(
    run_id: str,
    body: SubmitReviewRequest,
    runner: LocalRunner = Depends(get_runner),
):
    try:
        decision = ReviewDecision(body.decision)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid decision: {body.decision}"
        )
    try:
        result = runner.submit_review(run_id, decision)
    except RunnerError as exc:
        raise _map_runner_error(exc)
    return _serialize_run_result(result)


@router.post("/{run_id}/replay", response_model=ReplayResultResponse)
def replay_run(
    run_id: str,
    runner: LocalRunner = Depends(get_runner),
):
    try:
        result = runner.replay_run(run_id)
    except RunnerError as exc:
        raise _map_runner_error(exc)
    return _serialize_replay_result(result)


# ---------------------------------------------------------------------------
# Task 002 (Feature 015): Bundle endpoint
# ---------------------------------------------------------------------------


@router.get("/{run_id}/bundle")
def get_run_bundle(
    run_id: str,
    run_repo: AbstractRunRepository = Depends(get_run_repo),
    event_repo: AbstractEventRepository = Depends(get_event_repo),
    receipt_repo: AbstractReceiptRepository = Depends(get_receipt_repo),
):
    """Export replay bundle for a run (spec §25)."""
    try:
        bundle = assemble_bundle(run_id, run_repo, event_repo, receipt_repo)
    except BundleError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc))
    return bundle
