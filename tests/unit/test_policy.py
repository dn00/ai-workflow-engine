"""Tests for policy engine."""

from app.core.enums import ReasonCode
from app.workflows.access_request.policy import evaluate_policy
from app.workflows.access_request.reason_codes import AccessRequestReasonCode
from app.workflows.access_request.schema import NormalizedFields, Proposal
from app.workflows.access_request.validate import ValidationResult


def _make_valid_proposal() -> Proposal:
    """Helper: a fully valid proposal that qualifies for auto-approve."""
    return Proposal(
        request_type="access_request",
        employee_name="Jane Doe",
        systems_requested=["salesforce"],
        manager_name="Sarah Kim",
        start_date="2026-03-15",
        urgency="standard",
        justification="Need access",
        recommended_action="approve",
    )


def _make_valid_normalized() -> NormalizedFields:
    """Helper: normalized fields matching the valid proposal."""
    return NormalizedFields(
        employee_name="jane doe",
        systems_requested=["salesforce"],
        manager_name="sarah kim",
    )


def _valid_result() -> ValidationResult:
    """Helper: a passing validation result."""
    return ValidationResult(is_valid=True, errors=[])


class TestValidationFailureRejected:
    def test_validation_failure_rejected(self) -> None:
        proposal = _make_valid_proposal()
        normalized = _make_valid_normalized()
        validation = ValidationResult(
            is_valid=False,
            errors=["unsupported_request_type"],
        )
        result = evaluate_policy(proposal, normalized, validation)
        assert result.status == "rejected"
        assert "unsupported_request_type" in result.reason_codes
        assert result.allowed_actions == []


class TestMissingManagerReview:
    def test_missing_manager_review(self) -> None:
        proposal = _make_valid_proposal()
        normalized = NormalizedFields(
            employee_name="jane doe",
            systems_requested=["salesforce"],
            manager_name=None,
        )
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "review_required"
        assert AccessRequestReasonCode.MISSING_MANAGER_NAME in result.reason_codes


class TestHighUrgencyReview:
    def test_high_urgency_review(self) -> None:
        proposal = _make_valid_proposal()
        proposal.urgency = "high"
        normalized = _make_valid_normalized()
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "review_required"
        assert AccessRequestReasonCode.HIGH_URGENCY in result.reason_codes


class TestTooManySystemsReview:
    def test_too_many_systems_review(self) -> None:
        proposal = _make_valid_proposal()
        proposal.systems_requested = ["salesforce", "jira", "slack"]
        normalized = NormalizedFields(
            employee_name="jane doe",
            systems_requested=["salesforce", "jira", "slack"],
            manager_name="sarah kim",
        )
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "review_required"
        assert AccessRequestReasonCode.TOO_MANY_SYSTEMS in result.reason_codes


class TestAutoApproveAllConditions:
    def test_auto_approve_all_conditions(self) -> None:
        proposal = _make_valid_proposal()
        normalized = _make_valid_normalized()
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "approved"
        assert result.reason_codes == []
        assert result.allowed_actions == ["create_simulated_approval_task"]


class TestRejectedEmptyActions:
    def test_rejected_empty_actions(self) -> None:
        proposal = _make_valid_proposal()
        normalized = _make_valid_normalized()
        validation = ValidationResult(
            is_valid=False,
            errors=["unsupported_request_type"],
        )
        result = evaluate_policy(proposal, normalized, validation)
        assert result.status == "rejected"
        assert result.allowed_actions == []


class TestReviewCreateReviewTaskAction:
    def test_review_create_review_task_action(self) -> None:
        proposal = _make_valid_proposal()
        proposal.urgency = "high"
        normalized = _make_valid_normalized()
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "review_required"
        assert result.allowed_actions == ["create_review_task"]


class TestMultipleReviewTriggers:
    def test_multiple_review_triggers(self) -> None:
        proposal = _make_valid_proposal()
        proposal.urgency = "high"
        proposal.systems_requested = ["salesforce", "jira", "slack"]
        normalized = NormalizedFields(
            employee_name="jane doe",
            systems_requested=["salesforce", "jira", "slack"],
            manager_name=None,
        )
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "review_required"
        assert AccessRequestReasonCode.MISSING_MANAGER_NAME in result.reason_codes
        assert AccessRequestReasonCode.HIGH_URGENCY in result.reason_codes
        assert AccessRequestReasonCode.TOO_MANY_SYSTEMS in result.reason_codes


class TestKnownNotLowRiskReview:
    def test_known_not_low_risk_review(self) -> None:
        proposal = _make_valid_proposal()
        proposal.systems_requested = ["aws"]
        normalized = NormalizedFields(
            employee_name="jane doe",
            systems_requested=["aws"],
            manager_name="sarah kim",
        )
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "review_required"
        assert (
            AccessRequestReasonCode.MANAGER_APPROVAL_UNVERIFIED
            in result.reason_codes
        )


class TestNotesAmbiguityReview:
    def test_notes_ambiguity_review(self) -> None:
        proposal = _make_valid_proposal()
        proposal.notes = ["Employee start date is ambiguous"]
        normalized = _make_valid_normalized()
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "review_required"
        assert ReasonCode.AMBIGUOUS_NORMALIZATION in result.reason_codes


class TestUrgencyCaseInsensitive:
    def test_urgency_case_insensitive(self) -> None:
        proposal = _make_valid_proposal()
        proposal.urgency = "High"
        normalized = _make_valid_normalized()
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "review_required"
        assert AccessRequestReasonCode.HIGH_URGENCY in result.reason_codes


class TestTwoLowRiskSystemsApprove:
    def test_two_low_risk_systems_approve(self) -> None:
        proposal = _make_valid_proposal()
        proposal.systems_requested = ["salesforce", "jira"]
        normalized = NormalizedFields(
            employee_name="jane doe",
            systems_requested=["salesforce", "jira"],
            manager_name="sarah kim",
        )
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.status == "approved"


class TestEmptyNotesNoAmbiguity:
    def test_empty_notes_no_ambiguity(self) -> None:
        proposal = _make_valid_proposal()
        proposal.notes = []
        normalized = _make_valid_normalized()
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert ReasonCode.AMBIGUOUS_NORMALIZATION not in result.reason_codes

    def test_none_notes_no_ambiguity(self) -> None:
        proposal = _make_valid_proposal()
        proposal.notes = None
        normalized = _make_valid_normalized()
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert ReasonCode.AMBIGUOUS_NORMALIZATION not in result.reason_codes


class TestMultipleValidationErrorsForwarded:
    def test_multiple_validation_errors_forwarded(self) -> None:
        proposal = _make_valid_proposal()
        normalized = _make_valid_normalized()
        validation = ValidationResult(
            is_valid=False,
            errors=["unsupported_request_type", "missing_employee_name"],
        )
        result = evaluate_policy(proposal, normalized, validation)
        assert result.status == "rejected"
        assert "unsupported_request_type" in result.reason_codes
        assert "missing_employee_name" in result.reason_codes


class TestNormalizedFieldsAlwaysPresent:
    def test_normalized_fields_in_approved(self) -> None:
        proposal = _make_valid_proposal()
        normalized = _make_valid_normalized()
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.normalized_fields == normalized.model_dump()

    def test_normalized_fields_in_rejected(self) -> None:
        proposal = _make_valid_proposal()
        normalized = _make_valid_normalized()
        validation = ValidationResult(is_valid=False, errors=["bad"])
        result = evaluate_policy(proposal, normalized, validation)
        assert result.normalized_fields == normalized.model_dump()

    def test_normalized_fields_in_review(self) -> None:
        proposal = _make_valid_proposal()
        proposal.urgency = "high"
        normalized = _make_valid_normalized()
        result = evaluate_policy(proposal, normalized, _valid_result())
        assert result.normalized_fields == normalized.model_dump()
