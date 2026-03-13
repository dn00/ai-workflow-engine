"""Tests for field normalizer (Feature 006, Task 004)."""

from app.workflows.access_request.normalize import normalize_proposal
from app.workflows.access_request.schema import Proposal


class TestTask004AC1SystemsLowercased:
    """Task004 AC-1 test_systems_lowercased"""

    def test_mixed_case_systems(self) -> None:
        proposal = Proposal(systems_requested=["SalesForce", " LOOKER "])
        normalized = normalize_proposal(proposal)
        assert normalized.systems_requested == ["salesforce", "looker"]


class TestTask004AC2NamesStrippedAndCleaned:
    """Task004 AC-2 test_names_stripped_and_cleaned"""

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


class TestTask004EC1AlreadyNormalizedPassthrough:
    """Task004 EC-1 test_already_normalized_passthrough"""

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


class TestTask004EC2NoneManagerPreserved:
    """Task004 EC-2 test_none_manager_preserved"""

    def test_none_manager_stays_none(self) -> None:
        proposal = Proposal(employee_name="Jane Doe")
        normalized = normalize_proposal(proposal)
        assert normalized.manager_name is None


class TestTask004EC3NoneEmployeeBecomesEmpty:
    """Task004 EC-3 test_none_employee_becomes_empty"""

    def test_none_employee_name(self) -> None:
        proposal = Proposal()
        normalized = normalize_proposal(proposal)
        assert normalized.employee_name == ""


class TestTask004ERR1NoneSystemsBecomesEmptyList:
    """Task004 ERR-1 test_none_systems_becomes_empty_list"""

    def test_none_systems(self) -> None:
        proposal = Proposal()
        normalized = normalize_proposal(proposal)
        assert normalized.systems_requested == []
