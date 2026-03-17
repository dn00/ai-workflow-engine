"""Tests for core enums."""

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


class TestRunStatusHas10Values:
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


class TestEventTypeHas12Values:
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


class TestCoreReasonCodeHas4Values:
    def test_core_reason_code_has_4_values(self) -> None:
        assert len(ReasonCode) == 4

    def test_core_reason_code_exact_values(self) -> None:
        expected = {
            "malformed_date",
            "malformed_proposal",
            "ambiguous_normalization",
            "unsupported_request_type",
        }
        assert {m.value for m in ReasonCode} == expected


class TestOtherEnumsMemberCounts:
    def test_run_mode_has_3_values(self) -> None:
        assert len(RunMode) == 3

    def test_actor_type_has_4_values(self) -> None:
        assert len(ActorType) == 4

    def test_review_decision_has_2_values(self) -> None:
        assert len(ReviewDecision) == 2

    def test_review_status_has_2_values(self) -> None:
        assert len(ReviewStatus) == 2


class TestEnumStringSerialization:
    def test_str_returns_value(self) -> None:
        assert str(RunStatus.RECEIVED) == "received"

    def test_value_is_string(self) -> None:
        assert RunStatus.RECEIVED.value == "received"

    def test_event_type_dot_notation(self) -> None:
        assert str(EventType.RUN_RECEIVED) == "run.received"


class TestEnumHashable:
    def test_usable_as_dict_key(self) -> None:
        d = {RunStatus.RECEIVED: True}
        assert d[RunStatus.RECEIVED] is True

    def test_usable_in_set(self) -> None:
        s = {RunStatus.RECEIVED, RunStatus.COMPLETED}
        assert RunStatus.RECEIVED in s
        assert len(s) == 2


class TestInvalidEnumValueRaises:
    def test_invalid_run_status_raises(self) -> None:
        with pytest.raises(ValueError, match="nonexistent_status"):
            RunStatus("nonexistent_status")

    def test_invalid_event_type_raises(self) -> None:
        with pytest.raises(ValueError, match="not_an_event"):
            EventType("not_an_event")
