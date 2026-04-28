"""First-class workflow artifacts.

Artifacts are typed intermediate outputs produced during a run. They are
persisted for debugging, audit bundles, and future evaluation harnesses.
"""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class Artifact(BaseModel):
    """Inspectable intermediate output from a workflow run."""

    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    artifact_type: str
    schema_version: str = "1.0"
    data: dict
    source_receipt_id: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
