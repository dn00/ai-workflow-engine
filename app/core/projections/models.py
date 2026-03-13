"""RunProjection model — current derived state of a workflow run.

Built by folding events via reduce_events (spec §15, §16, §23).
"""

from pydantic import BaseModel

from app.core.enums import RunStatus


class RunProjection(BaseModel):
    """Current derived state of a workflow run, built by folding events."""

    run_id: str
    status: RunStatus = RunStatus.RECEIVED
    # Accumulated from event payloads
    proposal: dict | None = None
    validation_result: dict | None = None
    policy_decision: dict | None = None
    review_decision: str | None = None
    effect_result: dict | None = None
    error: dict | None = None
    # Metadata
    last_event_seq: int = 0
    event_count: int = 0
    version_info: dict | None = None
