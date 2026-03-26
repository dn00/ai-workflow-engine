"""Request/response Pydantic models for the /runs API surface (spec §25)."""

from datetime import datetime

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateRunRequest(BaseModel):
    """POST /runs request body."""

    input_text: str
    mode: str = "live"  # "live" or "dry_run"
    workflow_type: str = "access_request"


class SubmitReviewRequest(BaseModel):
    """POST /runs/{run_id}/review request body."""

    decision: str  # "approve" or "reject"


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RunResponse(BaseModel):
    """Serialized run summary."""

    run_id: str
    workflow_type: str
    status: str
    mode: str
    created_at: datetime
    updated_at: datetime
    current_projection: dict | None = None


class EventResponse(BaseModel):
    """Serialized event."""

    event_id: str
    run_id: str
    seq: int
    event_type: str
    timestamp: datetime
    actor_type: str
    payload: dict
    version_info: dict
    idempotency_key: str | None = None


class RunResultResponse(BaseModel):
    """Serialized RunResult (run + projection + optional review task)."""

    run: RunResponse
    projection: dict
    review_task: dict | None = None


class EventListResponse(BaseModel):
    """List of events for a run."""

    run_id: str
    events: list[EventResponse]


class ReplayResultResponse(BaseModel):
    """Serialized ReplayResult."""

    run_id: str
    replayed_projection: dict | None = None
    stored_projection: dict | None = None
    match: bool
    event_count: int
    error: str | None = None
