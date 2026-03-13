"""Tests for reducer-projection (Feature 008, Batch 01, Task 001)."""

from datetime import datetime, timezone

import pytest

from app.core.enums import ActorType, EventType, RunStatus
from app.core.models import Event, VersionInfo
from app.core.projections.reducer import (
    EVENT_STATUS_MAP,
    ReducerError,
    reduce_events,
)

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


def _review_approve_events(run_id: str = "run-1") -> list[Event]:
    """Full review-approve path: 8 events."""
    return [
        _make_event(run_id, 1, EventType.RUN_RECEIVED),
        _make_event(run_id, 2, EventType.PROPOSAL_GENERATED, {"raw": "proposal text"}),
        _make_event(run_id, 3, EventType.VALIDATION_COMPLETED, {"valid": True}),
        _make_event(run_id, 4, EventType.REVIEW_REQUESTED),
        _make_event(run_id, 5, EventType.REVIEW_APPROVED),
        _make_event(run_id, 6, EventType.EFFECT_REQUESTED),
        _make_event(run_id, 7, EventType.EFFECT_SIMULATED, {"changes": []}),
        _make_event(run_id, 8, EventType.RUN_COMPLETED),
    ]


def _rejection_events(run_id: str = "run-1") -> list[Event]:
    """Rejection path: 5 events."""
    return [
        _make_event(run_id, 1, EventType.RUN_RECEIVED),
        _make_event(run_id, 2, EventType.PROPOSAL_GENERATED, {"raw": "proposal text"}),
        _make_event(run_id, 3, EventType.VALIDATION_COMPLETED, {"valid": True}),
        _make_event(run_id, 4, EventType.DECISION_COMMITTED, {
            "status": "rejected",
            "reason_codes": ["policy_violation"],
            "normalized_fields": {},
            "allowed_actions": [],
        }),
        _make_event(run_id, 5, EventType.RUN_COMPLETED),
    ]


# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestTask001AC1AutoApprovePath:
    """Task001 AC-1 test_auto_approve_path_produces_correct_projection"""

    def test_auto_approve_path_produces_correct_projection(self) -> None:
        events = _auto_approve_events()
        proj = reduce_events(events)

        assert proj.run_id == "run-1"
        assert proj.status == RunStatus.COMPLETED
        assert proj.proposal == {"raw": "proposal text"}
        assert proj.validation_result == {"valid": True}
        assert proj.policy_decision is not None
        assert proj.policy_decision["status"] == "approved"
        assert proj.effect_result == {"changes": []}
        assert proj.event_count == 7


class TestTask001AC2ReviewApprovePath:
    """Task001 AC-2 test_review_approve_path_produces_correct_projection"""

    def test_review_approve_path_produces_correct_projection(self) -> None:
        events = _review_approve_events()
        proj = reduce_events(events)

        assert proj.run_id == "run-1"
        assert proj.status == RunStatus.COMPLETED
        assert proj.review_decision == "approve"


class TestTask001AC3RejectionPath:
    """Task001 AC-3 test_rejection_path_produces_correct_projection"""

    def test_rejection_path_produces_correct_projection(self) -> None:
        events = _rejection_events()
        proj = reduce_events(events)

        assert proj.run_id == "run-1"
        assert proj.status == RunStatus.COMPLETED
        assert proj.policy_decision is not None
        assert proj.policy_decision["status"] == "rejected"


class TestTask001AC4ParseFailure:
    """Task001 AC-4 test_parse_failure_produces_correct_projection"""

    def test_parse_failure_produces_correct_projection(self) -> None:
        events = [
            _make_event("run-1", 1, EventType.RUN_RECEIVED),
            _make_event("run-1", 2, EventType.PROPOSAL_PARSE_FAILED, {"error": "bad json"}),
        ]
        proj = reduce_events(events)

        assert proj.status == RunStatus.PROPOSAL_INVALID
        assert proj.error == {"error": "bad json"}


class TestTask001AC5ValidationFailure:
    """Task001 AC-5 test_validation_failure_produces_correct_projection"""

    def test_validation_failure_produces_correct_projection(self) -> None:
        events = [
            _make_event("run-1", 1, EventType.RUN_RECEIVED),
            _make_event("run-1", 2, EventType.PROPOSAL_GENERATED, {"raw": "text"}),
            _make_event("run-1", 3, EventType.VALIDATION_FAILED, {"reason": "invalid field"}),
        ]
        proj = reduce_events(events)

        assert proj.status == RunStatus.PROPOSAL_INVALID
        assert proj.error == {"reason": "invalid field"}


class TestTask001AC6EventTypeStatusMapping:
    """Task001 AC-6 test_each_event_type_maps_to_correct_status"""

    def test_direct_mapped_types(self) -> None:
        """All 11 direct-mapped event types produce correct RunStatus."""
        for event_type, expected_status in EVENT_STATUS_MAP.items():
            events = [_make_event("run-1", 1, event_type)]
            proj = reduce_events(events)
            assert proj.status == expected_status, (
                f"{event_type} should map to {expected_status}, got {proj.status}"
            )

    def test_decision_committed_approved(self) -> None:
        """decision.committed with status=approved maps to APPROVED."""
        events = [
            _make_event("run-1", 1, EventType.DECISION_COMMITTED, {
                "status": "approved",
                "reason_codes": [],
                "normalized_fields": {},
                "allowed_actions": [],
            }),
        ]
        proj = reduce_events(events)
        assert proj.status == RunStatus.APPROVED

    def test_decision_committed_review_required(self) -> None:
        """decision.committed with status=review_required maps to REVIEW_REQUIRED."""
        events = [
            _make_event("run-1", 1, EventType.DECISION_COMMITTED, {
                "status": "review_required",
                "reason_codes": [],
                "normalized_fields": {},
                "allowed_actions": [],
            }),
        ]
        proj = reduce_events(events)
        assert proj.status == RunStatus.REVIEW_REQUIRED

    def test_decision_committed_rejected(self) -> None:
        """decision.committed with status=rejected maps to REJECTED."""
        events = [
            _make_event("run-1", 1, EventType.DECISION_COMMITTED, {
                "status": "rejected",
                "reason_codes": [],
                "normalized_fields": {},
                "allowed_actions": [],
            }),
        ]
        proj = reduce_events(events)
        assert proj.status == RunStatus.REJECTED


class TestTask001AC7ProjectionSerializesToJson:
    """Task001 AC-7 test_projection_serializes_to_json_dict"""

    def test_projection_serializes_to_json_dict(self) -> None:
        events = _auto_approve_events()
        proj = reduce_events(events)
        dumped = proj.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["run_id"] == "run-1"
        assert dumped["status"] == RunStatus.COMPLETED
        assert dumped["event_count"] == 7
        # Verify all fields are present
        for field in [
            "run_id", "status", "proposal", "validation_result",
            "policy_decision", "review_decision", "effect_result",
            "error", "last_event_seq", "event_count", "version_info",
        ]:
            assert field in dumped


class TestTask001AC8DeterministicOutput:
    """Task001 AC-8 test_deterministic_output"""

    def test_deterministic_output(self) -> None:
        events = _auto_approve_events()
        proj1 = reduce_events(events)
        proj2 = reduce_events(events)
        assert proj1 == proj2


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestTask001EC1EmptyEventList:
    """Task001 EC-1 test_empty_event_list_raises_error"""

    def test_empty_event_list_raises_error(self) -> None:
        with pytest.raises(ReducerError, match="at least one event"):
            reduce_events([])


class TestTask001EC2DecisionCommittedMissingStatus:
    """Task001 EC-2 test_decision_committed_missing_status_raises_error"""

    def test_decision_committed_missing_status_raises_error(self) -> None:
        events = [
            _make_event("run-1", 1, EventType.DECISION_COMMITTED, {"reason_codes": []}),
        ]
        with pytest.raises(ReducerError, match="missing status"):
            reduce_events(events)


class TestTask001EC3PartialEventSequence:
    """Task001 EC-3 test_partial_event_sequence_mid_run"""

    def test_partial_event_sequence_mid_run(self) -> None:
        events = [
            _make_event("run-1", 1, EventType.RUN_RECEIVED),
            _make_event("run-1", 2, EventType.PROPOSAL_GENERATED, {"raw": "text"}),
            _make_event("run-1", 3, EventType.VALIDATION_COMPLETED, {"valid": True}),
        ]
        proj = reduce_events(events)

        assert proj.status == RunStatus.VALIDATED
        assert proj.policy_decision is None
        assert proj.effect_result is None
        assert proj.event_count == 3


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestTask001ERR1UnknownEventType:
    """Task001 ERR-1 test_unknown_event_type_raises_error"""

    def test_unknown_event_type_raises_error(self) -> None:
        # Use model_construct to bypass Pydantic enum validation
        event = Event.model_construct(
            event_id="evt-1",
            run_id="run-1",
            seq=1,
            event_type="unknown.event",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            version_info=VersionInfo(),
            payload={},
            actor_type=ActorType.SYSTEM,
            idempotency_key=None,
        )
        with pytest.raises(ReducerError, match="Unknown event type: unknown.event"):
            reduce_events([event])


class TestTask001ERR2MixedRunIds:
    """Task001 ERR-2 test_mixed_run_ids_raises_error"""

    def test_mixed_run_ids_raises_error(self) -> None:
        events = [
            _make_event("run-1", 1, EventType.RUN_RECEIVED),
            _make_event("run-2", 2, EventType.PROPOSAL_GENERATED),
        ]
        with pytest.raises(ReducerError, match="All events must belong to the same run"):
            reduce_events(events)
