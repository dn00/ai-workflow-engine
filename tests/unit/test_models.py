"""Tests for core models (Feature 002, Task 002)."""

import pytest
from pydantic import ValidationError

from app.core.enums import (
    ActorType,
    EventType,
    ReasonCode,
    ReviewStatus,
    RunMode,
    RunStatus,
)
from app.core.models import (
    Event,
    NormalizedFields,
    ReviewTask,
    Run,
    ValidatedDecision,
    VersionInfo,
)


class TestTask002AC1VersionInfoDefaultsAndCustom:
    """Task002 AC-1 test_version_info_defaults_and_custom"""

    def test_defaults(self) -> None:
        v = VersionInfo()
        assert v.proposal_schema_version == "1.0"
        assert v.prompt_version == "1.0"
        assert v.policy_version == "1.0"

    def test_custom_values(self) -> None:
        v = VersionInfo(
            proposal_schema_version="2.0",
            prompt_version="2.0",
            policy_version="2.0",
        )
        assert v.proposal_schema_version == "2.0"
        assert v.prompt_version == "2.0"
        assert v.policy_version == "2.0"


class TestTask002AC2EventValidatesWithRequiredFields:
    """Task002 AC-2 test_event_validates_with_required_fields"""

    def test_event_with_required_fields(self) -> None:
        e = Event(
            run_id="run-123",
            seq=1,
            event_type=EventType.RUN_RECEIVED,
            version_info=VersionInfo(),
            payload={"key": "value"},
            actor_type=ActorType.SYSTEM,
        )
        assert e.run_id == "run-123"
        assert e.seq == 1
        assert e.event_type == EventType.RUN_RECEIVED
        assert e.actor_type == ActorType.SYSTEM
        assert e.event_id  # auto-generated
        assert e.timestamp  # auto-generated


class TestTask002AC3RunDefaults:
    """Task002 AC-3 test_run_defaults"""

    def test_run_defaults(self) -> None:
        r = Run()
        assert r.run_id  # auto-generated UUID
        assert r.status == RunStatus.RECEIVED
        assert r.mode == RunMode.LIVE
        assert r.workflow_type == "access_request"
        assert r.created_at is not None
        assert r.updated_at is not None


class TestTask002AC4ValidatedDecisionSample:
    """Task002 AC-4 test_validated_decision_sample"""

    def test_sample_decision(self) -> None:
        d = ValidatedDecision(
            status="review_required",
            reason_codes=[
                ReasonCode.MANAGER_APPROVAL_UNVERIFIED,
                ReasonCode.HIGH_URGENCY,
            ],
            normalized_fields=NormalizedFields(
                employee_name="Jane Doe",
                systems_requested=["salesforce", "looker"],
                manager_name="Sarah Kim",
            ),
            allowed_actions=["create_review_task"],
        )
        assert d.status == "review_required"
        assert len(d.reason_codes) == 2
        assert d.reason_codes[0] == ReasonCode.MANAGER_APPROVAL_UNVERIFIED
        assert d.normalized_fields.employee_name == "Jane Doe"
        assert d.allowed_actions == ["create_review_task"]


class TestTask002AC5ReviewTaskDefaults:
    """Task002 AC-5 test_review_task_defaults"""

    def test_review_task_defaults(self) -> None:
        rt = ReviewTask(run_id="run-456")
        assert rt.review_id  # auto-generated
        assert rt.run_id == "run-456"
        assert rt.status == ReviewStatus.PENDING
        assert rt.decision is None
        assert rt.reviewed_at is None


class TestTask002EC1EventOptionalIdempotencyKey:
    """Task002 EC-1 test_event_optional_idempotency_key"""

    def test_idempotency_key_defaults_to_none(self) -> None:
        e = Event(
            run_id="run-123",
            seq=1,
            event_type=EventType.RUN_RECEIVED,
            version_info=VersionInfo(),
            payload={},
            actor_type=ActorType.SYSTEM,
        )
        assert e.idempotency_key is None


class TestTask002EC2RunOptionalProjection:
    """Task002 EC-2 test_run_optional_projection"""

    def test_projection_defaults_to_none(self) -> None:
        r = Run()
        assert r.current_projection is None


class TestTask002ERR1EventMissingRequiredField:
    """Task002 ERR-1 test_event_missing_required_field"""

    def test_missing_run_id_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Event(
                seq=1,
                event_type=EventType.RUN_RECEIVED,
                version_info=VersionInfo(),
                payload={},
                actor_type=ActorType.SYSTEM,
            )
        error_text = str(exc_info.value)
        assert "run_id" in error_text
