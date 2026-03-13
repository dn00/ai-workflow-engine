"""Core domain models for the AI Workflow Engine.

Pydantic models matching frozen spec §§13-16, 18.
"""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.enums import (
    ActorType,
    EventType,
    ReviewDecision,
    ReviewStatus,
    RunMode,
    RunStatus,
)


class VersionInfo(BaseModel):
    """Version tracking for proposal schema, prompt, and policy (spec §18)."""

    proposal_schema_version: str = "1.0"
    prompt_version: str = "1.0"
    policy_version: str = "1.0"


class ValidatedDecision(BaseModel):
    """Policy gate output (spec §14).

    Uses generic types so core stays workflow-agnostic.
    Workflow-specific NormalizedFields can be passed via .model_dump().
    StrEnum reason codes are accepted via str subclass coercion.
    """

    status: str
    reason_codes: list[str]
    normalized_fields: dict
    allowed_actions: list[str]


class Event(BaseModel):
    """Workflow event (spec §16 — 9 fields)."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    seq: int
    event_type: EventType
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    version_info: VersionInfo
    payload: dict
    actor_type: ActorType
    idempotency_key: str | None = None


class Run(BaseModel):
    """Workflow run (spec §13 runs table)."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_type: str = "access_request"
    status: RunStatus = RunStatus.RECEIVED
    mode: RunMode = RunMode.LIVE
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    current_projection: dict | None = None


class ReviewTask(BaseModel):
    """Review task (spec §13 reviews table)."""

    review_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    status: ReviewStatus = ReviewStatus.PENDING
    decision: ReviewDecision | None = None
    reviewed_at: datetime | None = None
