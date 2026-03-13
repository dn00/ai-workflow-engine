"""Replay engine — deterministic run reconstruction from stored events.

Pure Layer 2 function. No I/O, no LLM, no effects (INV-5.2–5.4).
Folds events via reduce_events and compares against stored projection (INV-5.5).
"""

from app.core.models import Event
from app.core.projections.reducer import ReducerError, reduce_events

from .models import ReplayResult


def replay_run(
    run_id: str,
    events: list[Event],
    stored_projection: dict | None,
) -> ReplayResult:
    """Replay a run by folding events and comparing against stored projection.

    Always returns a ReplayResult — never raises. Error cases are captured
    in the result's error field.

    Args:
        run_id: The run identifier.
        events: Ordered list of events for the run.
        stored_projection: The previously stored projection dict, or None.

    Returns:
        ReplayResult with replayed projection, match status, and any error.
    """
    if not events:
        return ReplayResult(
            run_id=run_id,
            stored_projection=stored_projection,
            error="cannot replay: no events provided",
        )

    try:
        projection = reduce_events(events)
    except ReducerError as exc:
        return ReplayResult(
            run_id=run_id,
            stored_projection=stored_projection,
            error=f"reducer error: {exc}",
        )

    replayed_dict = projection.model_dump(mode="json")
    match = (
        stored_projection is not None
        and replayed_dict == stored_projection
    )

    return ReplayResult(
        run_id=run_id,
        replayed_projection=projection,
        stored_projection=stored_projection,
        match=match,
        event_count=len(events),
    )
