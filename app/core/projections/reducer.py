"""Event-folding reducer — folds a sequence of Events into a RunProjection.

Pure Layer 2 function. No I/O, no side effects. Consumed by LocalRunner,
replay, and API (spec §15, §16, §23).
"""

from app.core.enums import EventType, RunStatus
from app.core.models import Event

from .models import RunProjection


class ReducerError(Exception):
    """Raised when the reducer encounters invalid input."""


EVENT_STATUS_MAP: dict[EventType, RunStatus] = {
    EventType.RUN_RECEIVED: RunStatus.RECEIVED,
    EventType.PROPOSAL_GENERATED: RunStatus.PROPOSAL_GENERATED,
    EventType.PROPOSAL_PARSE_FAILED: RunStatus.PROPOSAL_INVALID,
    EventType.VALIDATION_COMPLETED: RunStatus.VALIDATED,
    EventType.VALIDATION_FAILED: RunStatus.PROPOSAL_INVALID,
    EventType.REVIEW_REQUESTED: RunStatus.REVIEW_REQUIRED,
    EventType.REVIEW_APPROVED: RunStatus.APPROVED,
    EventType.REVIEW_REJECTED: RunStatus.REJECTED,
    EventType.EFFECT_REQUESTED: RunStatus.EFFECT_PENDING,
    EventType.EFFECT_SIMULATED: RunStatus.EFFECT_APPLIED,
    EventType.RUN_COMPLETED: RunStatus.COMPLETED,
}

# Maps decision.committed payload["status"] string → RunStatus
_DECISION_STATUS_MAP: dict[str, RunStatus] = {
    "approved": RunStatus.APPROVED,
    "review_required": RunStatus.REVIEW_REQUIRED,
    "rejected": RunStatus.REJECTED,
}


def reduce_events(events: list[Event]) -> RunProjection:
    """Fold a sequence of Events into a RunProjection.

    Args:
        events: Ordered list of events for a single run.

    Returns:
        RunProjection with accumulated state.

    Raises:
        ReducerError: If events list is empty, contains mixed run_ids,
            has unknown event types, or decision.committed lacks status.
    """
    if not events:
        raise ReducerError("at least one event is required")

    # Validate all events belong to the same run
    run_id = events[0].run_id
    for event in events[1:]:
        if event.run_id != run_id:
            raise ReducerError("All events must belong to the same run")

    projection = RunProjection(run_id=run_id)

    for event in events:
        _apply_event(projection, event)

    return projection


def _apply_event(projection: RunProjection, event: Event) -> None:
    """Apply a single event to the projection (mutates in place)."""
    event_type = event.event_type

    # Status transition
    if event_type == EventType.DECISION_COMMITTED:
        if "status" not in event.payload:
            raise ReducerError("missing status in decision payload")
        decision_status = event.payload["status"]
        mapped = _DECISION_STATUS_MAP.get(decision_status)
        if mapped is not None:
            projection.status = mapped
        else:
            projection.status = RunStatus(decision_status)
    elif event_type in EVENT_STATUS_MAP:
        projection.status = EVENT_STATUS_MAP[event_type]
    else:
        raise ReducerError(f"Unknown event type: {event_type}")

    # Payload accumulation
    if event_type == EventType.PROPOSAL_GENERATED:
        projection.proposal = event.payload
    elif event_type == EventType.VALIDATION_COMPLETED:
        projection.validation_result = event.payload
    elif event_type == EventType.VALIDATION_FAILED:
        projection.validation_result = event.payload
        projection.error = event.payload
    elif event_type == EventType.PROPOSAL_PARSE_FAILED:
        projection.error = event.payload
    elif event_type == EventType.DECISION_COMMITTED:
        projection.policy_decision = event.payload
    elif event_type == EventType.REVIEW_APPROVED:
        projection.review_decision = "approve"
    elif event_type == EventType.REVIEW_REJECTED:
        projection.review_decision = "reject"
    elif event_type == EventType.EFFECT_SIMULATED:
        projection.effect_result = event.payload

    # Metadata — always updated
    projection.version_info = event.version_info.model_dump()
    projection.last_event_seq = event.seq
    projection.event_count += 1
