"""Tests for schema validator."""

from app.core.enums import ReasonCode
from app.workflows.access_request.normalize import normalize_proposal
from app.workflows.access_request.reason_codes import AccessRequestReasonCode
from app.workflows.access_request.schema import NormalizedFields, Proposal
from app.workflows.access_request.validate import validate_proposal


def _make_valid_proposal() -> Proposal:
    """Helper: a fully valid proposal."""
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
        employee_name="Jane Doe",
        systems_requested=["salesforce"],
        manager_name="Sarah Kim",
    )


class TestValidProposalPasses:
    def test_full_valid_proposal(self) -> None:
        proposal = _make_valid_proposal()
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is True
        assert result.errors == []


class TestUnsupportedRequestType:
    def test_invoice_request_type(self) -> None:
        proposal = _make_valid_proposal()
        proposal.request_type = "invoice"
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert ReasonCode.UNSUPPORTED_REQUEST_TYPE in result.errors


class TestMissingEmployeeName:
    def test_empty_employee_name(self) -> None:
        proposal = _make_valid_proposal()
        proposal.employee_name = None
        normalized = normalize_proposal(proposal)
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert len(result.errors) >= 1


class TestNoSystemsRequested:
    def test_no_systems(self) -> None:
        proposal = _make_valid_proposal()
        proposal.systems_requested = None
        normalized = normalize_proposal(proposal)
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert len(result.errors) >= 1


class TestUnknownSystem:
    def test_unknown_app(self) -> None:
        proposal = _make_valid_proposal()
        proposal.systems_requested = ["unknown_app"]
        normalized = NormalizedFields(
            employee_name="Jane Doe",
            systems_requested=["unknown_app"],
            manager_name="Sarah Kim",
        )
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert AccessRequestReasonCode.UNKNOWN_SYSTEM in result.errors


class TestForbiddenSystem:
    def test_admin_console(self) -> None:
        proposal = _make_valid_proposal()
        proposal.systems_requested = ["admin_console"]
        normalized = NormalizedFields(
            employee_name="Jane Doe",
            systems_requested=["admin_console"],
            manager_name="Sarah Kim",
        )
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert AccessRequestReasonCode.FORBIDDEN_SYSTEM in result.errors


class TestMalformedDate:
    def test_invalid_date_string(self) -> None:
        proposal = _make_valid_proposal()
        proposal.start_date = "not-a-date"
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert ReasonCode.MALFORMED_DATE in result.errors


class TestValidDatePasses:
    def test_iso_date(self) -> None:
        proposal = _make_valid_proposal()
        proposal.start_date = "2026-03-12"
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert ReasonCode.MALFORMED_DATE not in result.errors


class TestNoDateIsOk:
    def test_none_date(self) -> None:
        proposal = _make_valid_proposal()
        proposal.start_date = None
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert ReasonCode.MALFORMED_DATE not in result.errors


class TestMixedKnownAndForbidden:
    def test_salesforce_and_admin_console(self) -> None:
        proposal = _make_valid_proposal()
        proposal.systems_requested = ["salesforce", "admin_console"]
        normalized = NormalizedFields(
            employee_name="Jane Doe",
            systems_requested=["salesforce", "admin_console"],
            manager_name="Sarah Kim",
        )
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert AccessRequestReasonCode.FORBIDDEN_SYSTEM in result.errors


class TestMultipleErrorsAccumulated:
    def test_bad_type_and_missing_name(self) -> None:
        proposal = Proposal(
            request_type="invoice",
            employee_name=None,
            systems_requested=["salesforce"],
        )
        normalized = normalize_proposal(proposal)
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert len(result.errors) >= 2
        assert ReasonCode.UNSUPPORTED_REQUEST_TYPE in result.errors


class TestCompletelyEmptyProposal:
    def test_all_none(self) -> None:
        proposal = Proposal()
        normalized = normalize_proposal(proposal)
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert len(result.errors) >= 3


class TestNoneRequestTypeUnsupported:
    def test_none_request_type(self) -> None:
        proposal = _make_valid_proposal()
        proposal.request_type = None
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert ReasonCode.UNSUPPORTED_REQUEST_TYPE in result.errors
