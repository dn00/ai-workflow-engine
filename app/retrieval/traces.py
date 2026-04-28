"""Retrieval trace records."""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class RetrievalTrace(BaseModel):
    """Append-only trace for one retrieval call."""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str | None = None
    workflow_type: str
    query: str
    top_k: int
    filters: dict = Field(default_factory=dict)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    sufficient: bool
    reason: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
