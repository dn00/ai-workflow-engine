"""LLM trace records.

Traces explain model-boundary behavior. They are not workflow state and must not
be used as a source of truth for policy or replay decisions.
"""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class LLMTrace(BaseModel):
    """Append-only trace for one LLM proposal generation attempt."""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    workflow_type: str
    prompt_version: str | None = None
    model_id: str | None = None
    latency_ms: int
    input_chars: int
    response_chars: int | None = None
    parse_success: bool | None = None
    parse_error: str | None = None
    policy_status: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
