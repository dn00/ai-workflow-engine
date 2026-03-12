"""Tests for core enums (Feature 002, Task 001)."""

import pytest

from app.core.enums import (
    ActorType,
    EventType,
    ReasonCode,
    ReviewDecision,
    ReviewStatus,
    RunMode,
    RunStatus,
)


class TestTask001AC1RunStatusHas10Values:
    """Task001 AC-1 test_run_status_has_10_values"""

    def test_run_status_has_10_values(self) -> None:
        assert len(RunStatus) == 10

    def test_run_status_exact_values(self) -> None:
        expected = {
            "received",
            "proposal_generated",
            "proposal_invalid",
            "validated",
            "review_required",
            "approved",
            "rejected",
            "effect_pending",
            "effect_applied",
            "completed",
        }
        assert {m.value for m in RunStatus} == expected


class TestTask001AC2EventTypeHas12Values:
    """Task001 AC-2 test_event_type_has_12_values"""

    def test_event_type_has_12_values(self) -> None:
        assert len(EventType) == 12

    def test_event_type_exact_values(self) -> None:
        expected = {
            "run.received",
            "proposal.generated",
            "proposal.parse_failed",
            "validation.completed",
            "validation.failed",
            "review.requested",
            "review.approved",
            "review.rejected",
            "decision.committed",
            "effect.requested",
            "effect.simulated",
            "run.completed",
        }
        assert {m.value for m in EventType} == expected


class TestTask001AC3ReasonCodeHas10Values:
    """Task001 AC-3 test_reason_code_has_10_values"""

    def test_reason_code_has_10_values(self) -> None:
        assert len(ReasonCode) == 10

    def test_reason_code_exact_values(self) -> None:
        expected = {
            "missing_manager_name",
            "high_urgency",
            "too_many_systems",
            "unknown_system",
            "forbidden_system",
            "malformed_date",
            "malformed_proposal",
            "ambiguous_normalization",
            "unsupported_request_type",
            "manager_approval_unverified",
        }
        assert {m.value for m in ReasonCode} == expected


class TestTask001AC4OtherEnumsMemberCounts:
    """Task001 AC-4 test_other_enums_member_counts"""

    def test_run_mode_has_3_values(self) -> None:
        assert len(RunMode) == 3

    def test_actor_type_has_4_values(self) -> None:
        assert len(ActorType) == 4

    def test_review_decision_has_2_values(self) -> None:
        assert len(ReviewDecision) == 2

    def test_review_status_has_2_values(self) -> None:
        assert len(ReviewStatus) == 2


class TestTask001EC1EnumStringSerialization:
    """Task001 EC-1 test_enum_string_serialization"""

    def test_str_returns_value(self) -> None:
        assert str(RunStatus.RECEIVED) == "received"

    def test_value_is_string(self) -> None:
        assert RunStatus.RECEIVED.value == "received"

    def test_event_type_dot_notation(self) -> None:
        assert str(EventType.RUN_RECEIVED) == "run.received"


class TestTask001EC2EnumHashable:
    """Task001 EC-2 test_enum_hashable"""

    def test_usable_as_dict_key(self) -> None:
        d = {RunStatus.RECEIVED: True}
        assert d[RunStatus.RECEIVED] is True

    def test_usable_in_set(self) -> None:
        s = {RunStatus.RECEIVED, RunStatus.COMPLETED}
        assert RunStatus.RECEIVED in s
        assert len(s) == 2


class TestTask001ERR1InvalidEnumValueRaises:
    """Task001 ERR-1 test_invalid_enum_value_raises"""

    def test_invalid_run_status_raises(self) -> None:
        with pytest.raises(ValueError, match="nonexistent_status"):
            RunStatus("nonexistent_status")

    def test_invalid_event_type_raises(self) -> None:
        with pytest.raises(ValueError, match="not_an_event"):
            EventType("not_an_event")
