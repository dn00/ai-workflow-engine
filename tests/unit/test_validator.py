"""Tests for schema validator (Feature 006, Task 005)."""

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


class TestTask005AC1ValidProposalPasses:
    """Task005 AC-1 test_valid_proposal_passes"""

    def test_full_valid_proposal(self) -> None:
        proposal = _make_valid_proposal()
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is True
        assert result.errors == []


class TestTask005AC2UnsupportedRequestType:
    """Task005 AC-2 test_unsupported_request_type"""

    def test_invoice_request_type(self) -> None:
        proposal = _make_valid_proposal()
        proposal.request_type = "invoice"
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert ReasonCode.UNSUPPORTED_REQUEST_TYPE in result.errors


class TestTask005AC3MissingEmployeeName:
    """Task005 AC-3 test_missing_employee_name"""

    def test_empty_employee_name(self) -> None:
        proposal = _make_valid_proposal()
        proposal.employee_name = None
        normalized = normalize_proposal(proposal)
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert len(result.errors) >= 1


class TestTask005AC4NoSystemsRequested:
    """Task005 AC-4 test_no_systems_requested"""

    def test_no_systems(self) -> None:
        proposal = _make_valid_proposal()
        proposal.systems_requested = None
        normalized = normalize_proposal(proposal)
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert len(result.errors) >= 1


class TestTask005AC5UnknownSystem:
    """Task005 AC-5 test_unknown_system"""

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


class TestTask005EC1ForbiddenSystem:
    """Task005 EC-1 test_forbidden_system"""

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


class TestTask005EC2MalformedDate:
    """Task005 EC-2 test_malformed_date"""

    def test_invalid_date_string(self) -> None:
        proposal = _make_valid_proposal()
        proposal.start_date = "not-a-date"
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert ReasonCode.MALFORMED_DATE in result.errors


class TestTask005EC3ValidDatePasses:
    """Task005 EC-3 test_valid_date_passes"""

    def test_iso_date(self) -> None:
        proposal = _make_valid_proposal()
        proposal.start_date = "2026-03-12"
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert ReasonCode.MALFORMED_DATE not in result.errors


class TestTask005EC4NoDateIsOk:
    """Task005 EC-4 test_no_date_is_ok"""

    def test_none_date(self) -> None:
        proposal = _make_valid_proposal()
        proposal.start_date = None
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert ReasonCode.MALFORMED_DATE not in result.errors


class TestTask005EC5MixedKnownAndForbidden:
    """Task005 EC-5 test_mixed_known_and_forbidden"""

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


class TestTask005ERR1MultipleErrorsAccumulated:
    """Task005 ERR-1 test_multiple_errors_accumulated"""

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


class TestTask005ERR2CompletelyEmptyProposal:
    """Task005 ERR-2 test_completely_empty_proposal"""

    def test_all_none(self) -> None:
        proposal = Proposal()
        normalized = normalize_proposal(proposal)
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert len(result.errors) >= 3


class TestTask005ERR3NoneRequestTypeUnsupported:
    """Task005 ERR-3 test_none_request_type_unsupported"""

    def test_none_request_type(self) -> None:
        proposal = _make_valid_proposal()
        proposal.request_type = None
        normalized = _make_valid_normalized()
        result = validate_proposal(proposal, normalized)
        assert result.is_valid is False
        assert ReasonCode.UNSUPPORTED_REQUEST_TYPE in result.errors
