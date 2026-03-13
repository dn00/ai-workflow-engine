"""Tests for proposal parser (Feature 006, Task 003)."""

import json

from app.workflows.access_request.parse import parse_proposal


class TestTask003AC1ValidJsonParses:
    """Task003 AC-1 test_valid_json_parses"""

    def test_valid_full_proposal(self) -> None:
        data = {
            "request_type": "access_request",
            "employee_name": "Jane Doe",
            "systems_requested": ["salesforce", "looker"],
            "manager_name": "Sarah Kim",
            "start_date": "2026-03-15",
            "urgency": "standard",
            "justification": "Need access for project",
            "recommended_action": "approve",
            "notes": ["First request"],
        }
        result = parse_proposal(json.dumps(data))
        assert result.success is True
        assert result.proposal is not None
        assert result.proposal.employee_name == "Jane Doe"
        assert result.proposal.systems_requested == ["salesforce", "looker"]
        assert result.error is None


class TestTask003AC2PartialFieldsParse:
    """Task003 AC-2 test_partial_fields_parse"""

    def test_only_request_type_and_name(self) -> None:
        data = {"request_type": "access_request", "employee_name": "Jane Doe"}
        result = parse_proposal(json.dumps(data))
        assert result.success is True
        assert result.proposal is not None
        assert result.proposal.request_type == "access_request"
        assert result.proposal.employee_name == "Jane Doe"
        assert result.proposal.systems_requested is None
        assert result.proposal.manager_name is None


class TestTask003EC1ExtraFieldsIgnored:
    """Task003 EC-1 test_extra_fields_ignored"""

    def test_extra_field_dropped(self) -> None:
        data = {"request_type": "access_request", "extra_field": "value"}
        result = parse_proposal(json.dumps(data))
        assert result.success is True
        assert result.proposal is not None
        assert result.proposal.request_type == "access_request"
        assert not hasattr(result.proposal, "extra_field")


class TestTask003EC2EmptyObjectParses:
    """Task003 EC-2 test_empty_object_parses"""

    def test_empty_json_object(self) -> None:
        result = parse_proposal("{}")
        assert result.success is True
        assert result.proposal is not None
        assert result.proposal.request_type is None
        assert result.proposal.employee_name is None


class TestTask003ERR1MalformedJsonError:
    """Task003 ERR-1 test_malformed_json_error"""

    def test_not_json(self) -> None:
        result = parse_proposal("not json at all")
        assert result.success is False
        assert result.proposal is None
        assert result.error is not None
        assert "json" in result.error.lower() or "parse" in result.error.lower()


class TestTask003ERR2TypeInvalidJsonError:
    """Task003 ERR-2 test_type_invalid_json_error"""

    def test_systems_as_string(self) -> None:
        data = {"systems_requested": "not-a-list"}
        result = parse_proposal(json.dumps(data))
        assert result.success is False
        assert result.proposal is None
        assert result.error is not None
        assert "systems_requested" in result.error
