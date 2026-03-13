"""ReplayResult model — result of replaying a run from stored events.

Pure Layer 2 model. No I/O. Used by replay engine (spec §23, INV-5.2–5.5).
"""

from pydantic import BaseModel

from app.core.projections.models import RunProjection


class ReplayResult(BaseModel):
    """Result of replaying a run from stored events."""

    run_id: str
    replayed_projection: RunProjection | None = None
    stored_projection: dict | None = None
    match: bool = False
    event_count: int = 0
    error: str | None = None
