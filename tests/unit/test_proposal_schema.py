"""Tests for Proposal schema (Feature 002, Task 003)."""

import pytest
from pydantic import ValidationError

from app.workflows.access_request.schema import Proposal


FULL_SAMPLE = {
    "request_type": "access_request",
    "employee_name": "Jane Doe",
    "systems_requested": ["Salesforce", "Looker"],
    "manager_name": "Sarah Kim",
    "start_date": "2026-03-12",
    "urgency": "high",
    "justification": "Revenue Ops onboarding",
    "recommended_action": "manager_review",
    "notes": ["Employee start date is near-term"],
}


class TestTask003AC1ProposalFullSample:
    """Task003 AC-1 test_proposal_full_sample"""

    def test_full_sample_validates(self) -> None:
        p = Proposal(**FULL_SAMPLE)
        assert p.request_type == "access_request"
        assert p.employee_name == "Jane Doe"
        assert p.systems_requested == ["Salesforce", "Looker"]
        assert p.manager_name == "Sarah Kim"
        assert p.start_date == "2026-03-12"
        assert p.urgency == "high"
        assert p.justification == "Revenue Ops onboarding"
        assert p.recommended_action == "manager_review"
        assert p.notes == ["Employee start date is near-term"]


class TestTask003AC2ProposalPartialData:
    """Task003 AC-2 test_proposal_partial_data"""

    def test_partial_data_validates(self) -> None:
        p = Proposal(request_type="access_request", employee_name="Jane Doe")
        assert p.request_type == "access_request"
        assert p.employee_name == "Jane Doe"
        assert p.systems_requested is None
        assert p.manager_name is None
        assert p.urgency is None


class TestTask003AC3ProposalJsonRoundtrip:
    """Task003 AC-3 test_proposal_json_roundtrip"""

    def test_roundtrip(self) -> None:
        original = Proposal(**FULL_SAMPLE)
        dumped = original.model_dump()
        reconstructed = Proposal(**dumped)
        assert original == reconstructed


class TestTask003EC1ProposalEmptyLists:
    """Task003 EC-1 test_proposal_empty_lists"""

    def test_empty_lists_preserved(self) -> None:
        p = Proposal(systems_requested=[], notes=[])
        assert p.systems_requested == []
        assert p.notes == []


class TestTask003EC2ProposalAllNone:
    """Task003 EC-2 test_proposal_all_none"""

    def test_all_none(self) -> None:
        p = Proposal()
        assert p.request_type is None
        assert p.employee_name is None
        assert p.systems_requested is None
        assert p.manager_name is None
        assert p.start_date is None
        assert p.urgency is None
        assert p.justification is None
        assert p.recommended_action is None
        assert p.notes is None


class TestTask003ERR1ProposalWrongTypes:
    """Task003 ERR-1 test_proposal_wrong_types"""

    def test_wrong_type_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Proposal(systems_requested="not-a-list")
        error_text = str(exc_info.value)
        assert "systems_requested" in error_text
