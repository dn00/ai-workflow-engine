"""Response schemas for read-only observability endpoints."""

from datetime import datetime

from pydantic import BaseModel


class LLMTraceResponse(BaseModel):
    """Serialized LLM trace."""

    trace_id: str
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
    reason_codes: list[str]
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime


class LLMTraceListResponse(BaseModel):
    """List response for LLM traces."""

    traces: list[LLMTraceResponse]
