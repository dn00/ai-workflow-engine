"""Receipt domain model (Feature 013, Spec §17)."""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class Receipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    raw_response: str
    prompt_version: str
    model_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
