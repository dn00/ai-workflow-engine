"""Tests for replay-engine (Feature 011, Batch 01, Task 001)."""

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel

from app.core.enums import ActorType, EventType, RunStatus
from app.core.models import Event, VersionInfo
from app.core.projections.models import RunProjection
from app.core.projections.reducer import reduce_events
from app.core.replay.engine import replay_run
from app.core.replay.models import ReplayResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    run_id: str,
    seq: int,
    event_type: EventType,
    payload: dict | None = None,
) -> Event:
    """Create a minimal Event for testing."""
    return Event(
        run_id=run_id,
        seq=seq,
        event_type=event_type,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        version_info=VersionInfo(),
        payload=payload or {},
        actor_type=ActorType.SYSTEM,
    )


def _auto_approve_events(run_id: str = "run-1") -> list[Event]:
    """Full auto-approve path: 7 events."""
    return [
        _make_event(run_id, 1, EventType.RUN_RECEIVED),
        _make_event(run_id, 2, EventType.PROPOSAL_GENERATED, {"raw": "proposal text"}),
        _make_event(run_id, 3, EventType.VALIDATION_COMPLETED, {"valid": True}),
        _make_event(run_id, 4, EventType.DECISION_COMMITTED, {
            "status": "approved",
            "reason_codes": [],
            "normalized_fields": {},
            "allowed_actions": ["apply"],
        }),
        _make_event(run_id, 5, EventType.EFFECT_REQUESTED),
        _make_event(run_id, 6, EventType.EFFECT_SIMULATED, {"changes": []}),
        _make_event(run_id, 7, EventType.RUN_COMPLETED),
    ]


def _review_path_events(run_id: str = "run-1") -> list[Event]:
    """Review path: decision→review_required, then review.approved, then second decision→approved."""
    return [
        _make_event(run_id, 1, EventType.RUN_RECEIVED),
        _make_event(run_id, 2, EventType.PROPOSAL_GENERATED, {"raw": "proposal text"}),
        _make_event(run_id, 3, EventType.VALIDATION_COMPLETED, {"valid": True}),
        _make_event(run_id, 4, EventType.DECISION_COMMITTED, {
            "status": "review_required",
            "reason_codes": [],
            "normalized_fields": {},
            "allowed_actions": [],
        }),
        _make_event(run_id, 5, EventType.REVIEW_REQUESTED),
        _make_event(run_id, 6, EventType.REVIEW_APPROVED),
        _make_event(run_id, 7, EventType.DECISION_COMMITTED, {
            "status": "approved",
            "reason_codes": [],
            "normalized_fields": {},
            "allowed_actions": ["apply"],
        }),
        _make_event(run_id, 8, EventType.EFFECT_REQUESTED),
        _make_event(run_id, 9, EventType.EFFECT_SIMULATED, {"changes": []}),
        _make_event(run_id, 10, EventType.RUN_COMPLETED),
    ]


# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------

class TestReplayResultModel:
    """Task001 AC-1 test_replay_result_model_construction"""

    def test_replay_result_is_pydantic_basemodel(self) -> None:
        result = ReplayResult(run_id="run-1")
        assert isinstance(result, BaseModel)

    def test_replay_result_fields(self) -> None:
        projection = RunProjection(run_id="run-1")
        stored = {"run_id": "run-1", "status": "received"}
        result = ReplayResult(
            run_id="run-1",
            replayed_projection=projection,
            stored_projection=stored,
            match=True,
            event_count=5,
            error=None,
        )
        assert result.run_id == "run-1"
        assert result.replayed_projection == projection
        assert result.stored_projection == stored
        assert result.match is True
        assert result.event_count == 5
        assert result.error is None

    def test_replay_result_defaults(self) -> None:
        result = ReplayResult(run_id="run-1")
        assert result.replayed_projection is None
        assert result.stored_projection is None
        assert result.match is False
        assert result.event_count == 0
        assert result.error is None


class TestReplayProducesProjection:
    """Task001 AC-2 test_replay_produces_correct_projection"""

    def test_replay_produces_correct_projection(self) -> None:
        events = _auto_approve_events("run-1")
        expected = reduce_events(events)
        stored = expected.model_dump(mode="json")

        result = replay_run("run-1", events, stored)

        assert result.replayed_projection is not None
        assert result.replayed_projection.model_dump(mode="json") == expected.model_dump(mode="json")
        assert result.event_count == 7


class TestReplayDetectsMatch:
    """Task001 AC-3 test_replay_detects_match"""

    def test_replay_detects_match(self) -> None:
        events = _auto_approve_events("run-1")
        projection = reduce_events(events)
        stored = projection.model_dump(mode="json")

        result = replay_run("run-1", events, stored)

        assert result.match is True
        assert result.error is None


class TestReplayDetectsMismatch:
    """Task001 AC-4 test_replay_detects_mismatch"""

    def test_replay_detects_mismatch(self) -> None:
        events = _auto_approve_events("run-1")
        projection = reduce_events(events)
        stored = projection.model_dump(mode="json")
        # Tamper with stored projection to cause mismatch
        stored["status"] = "received"

        result = replay_run("run-1", events, stored)

        assert result.match is False
        assert result.error is None
        assert result.replayed_projection is not None


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------

class TestStoredProjectionNone:
    """Task001 EC-1 test_stored_projection_none"""

    def test_stored_projection_none(self) -> None:
        events = _auto_approve_events("run-1")

        result = replay_run("run-1", events, None)

        assert result.match is False
        assert result.replayed_projection is not None
        assert result.error is None


class TestSingleEventReplay:
    """Task001 EC-2 test_single_event_replay"""

    def test_single_event_replay(self) -> None:
        events = [_make_event("run-1", 1, EventType.RUN_RECEIVED)]
        projection = reduce_events(events)
        stored = projection.model_dump(mode="json")

        result = replay_run("run-1", events, stored)

        assert result.replayed_projection is not None
        assert result.replayed_projection.status == RunStatus.RECEIVED
        assert result.event_count == 1
        assert result.match is True


class TestReviewPathReplay:
    """Task001 EC-3 test_review_path_replay"""

    def test_review_path_replay(self) -> None:
        events = _review_path_events("run-1")
        projection = reduce_events(events)
        stored = projection.model_dump(mode="json")

        result = replay_run("run-1", events, stored)

        assert result.replayed_projection is not None
        assert result.replayed_projection.status == RunStatus.COMPLETED
        assert result.replayed_projection.review_decision == "approve"
        assert result.match is True


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------

class TestEmptyEventsError:
    """Task001 ERR-1 test_empty_events_error"""

    def test_empty_events_error(self) -> None:
        result = replay_run("run-1", [], None)

        assert result.error is not None
        assert "no events" in result.error
        assert result.match is False
        assert result.replayed_projection is None


class TestReducerErrorWrapped:
    """Task001 ERR-2 test_reducer_error_wrapped"""

    def test_reducer_error_wrapped(self) -> None:
        events = [
            _make_event("run-1", 1, EventType.RUN_RECEIVED),
            _make_event("run-2", 2, EventType.PROPOSAL_GENERATED, {"raw": "x"}),
        ]

        result = replay_run("run-1", events, None)

        assert result.error is not None
        assert result.error.startswith("reducer error:")
        assert result.match is False
        assert result.replayed_projection is None
