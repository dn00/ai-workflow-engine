"""Tests for core models."""

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
    ReviewTask,
    Run,
    ValidatedDecision,
    VersionInfo,
)


class TestVersionInfoDefaultsAndCustom:
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


class TestEventValidatesWithRequiredFields:
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


class TestRunDefaults:
    def test_run_defaults(self) -> None:
        r = Run()
        assert r.run_id  # auto-generated UUID
        assert r.status == RunStatus.RECEIVED
        assert r.mode == RunMode.LIVE
        assert r.workflow_type == "access_request"
        assert r.created_at is not None
        assert r.updated_at is not None


class TestValidatedDecisionSample:
    def test_sample_decision(self) -> None:
        d = ValidatedDecision(
            status="review_required",
            reason_codes=[
                "manager_approval_unverified",
                "high_urgency",
            ],
            normalized_fields={
                "employee_name": "Jane Doe",
                "systems_requested": ["salesforce", "looker"],
                "manager_name": "Sarah Kim",
            },
            allowed_actions=["create_review_task"],
        )
        assert d.status == "review_required"
        assert len(d.reason_codes) == 2
        assert d.reason_codes[0] == "manager_approval_unverified"
        assert d.normalized_fields["employee_name"] == "Jane Doe"
        assert d.allowed_actions == ["create_review_task"]


class TestReviewTaskDefaults:
    def test_review_task_defaults(self) -> None:
        rt = ReviewTask(run_id="run-456")
        assert rt.review_id  # auto-generated
        assert rt.run_id == "run-456"
        assert rt.status == ReviewStatus.PENDING
        assert rt.decision is None
        assert rt.reviewed_at is None


class TestEventOptionalIdempotencyKey:
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


class TestRunOptionalProjection:
    def test_projection_defaults_to_none(self) -> None:
        r = Run()
        assert r.current_projection is None


class TestEventMissingRequiredField:
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


class TestValidatedDecisionGenericTypes:
    def test_accepts_string_reason_codes_and_dict(self) -> None:
        d = ValidatedDecision(
            status="approved",
            reason_codes=["custom_reason_1", "custom_reason_2"],
            normalized_fields={"some_field": "value", "count": 42},
            allowed_actions=["do_something"],
        )
        assert d.reason_codes == ["custom_reason_1", "custom_reason_2"]
        assert d.normalized_fields == {"some_field": "value", "count": 42}

    def test_accepts_empty_reason_codes_and_fields(self) -> None:
        d = ValidatedDecision(
            status="validated",
            reason_codes=[],
            normalized_fields={},
            allowed_actions=[],
        )
        assert d.reason_codes == []
        assert d.normalized_fields == {}


class TestStrEnumAcceptedAsStr:
    def test_strenum_in_reason_codes(self) -> None:
        d = ValidatedDecision(
            status="validated",
            reason_codes=[ReasonCode.MALFORMED_DATE],
            normalized_fields={},
            allowed_actions=[],
        )
        assert d.reason_codes[0] == "malformed_date"
