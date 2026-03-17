"""Tests for field normalizer."""

from app.workflows.access_request.normalize import normalize_proposal
from app.workflows.access_request.schema import Proposal


class TestSystemsLowercased:
    def test_mixed_case_systems(self) -> None:
        proposal = Proposal(systems_requested=["SalesForce", " LOOKER "])
        normalized = normalize_proposal(proposal)
        assert normalized.systems_requested == ["salesforce", "looker"]


class TestNamesStrippedAndCleaned:
    def test_excess_whitespace_in_name(self) -> None:
        proposal = Proposal(employee_name="  Jane   Doe  ")
        normalized = normalize_proposal(proposal)
        assert normalized.employee_name == "Jane Doe"

    def test_manager_name_cleaned(self) -> None:
        proposal = Proposal(
            employee_name="Jane Doe",
            manager_name="  Sarah   Kim  ",
        )
        normalized = normalize_proposal(proposal)
        assert normalized.manager_name == "Sarah Kim"


class TestAlreadyNormalizedPassthrough:
    def test_clean_values_unchanged(self) -> None:
        proposal = Proposal(
            employee_name="Jane Doe",
            systems_requested=["salesforce"],
            manager_name="Sarah Kim",
        )
        normalized = normalize_proposal(proposal)
        assert normalized.employee_name == "Jane Doe"
        assert normalized.systems_requested == ["salesforce"]
        assert normalized.manager_name == "Sarah Kim"


class TestNoneManagerPreserved:
    def test_none_manager_stays_none(self) -> None:
        proposal = Proposal(employee_name="Jane Doe")
        normalized = normalize_proposal(proposal)
        assert normalized.manager_name is None


class TestNoneEmployeeBecomesEmpty:
    def test_none_employee_name(self) -> None:
        proposal = Proposal()
        normalized = normalize_proposal(proposal)
        assert normalized.employee_name == ""


class TestNoneSystemsBecomesEmptyList:
    def test_none_systems(self) -> None:
        proposal = Proposal()
        normalized = normalize_proposal(proposal)
        assert normalized.systems_requested == []
