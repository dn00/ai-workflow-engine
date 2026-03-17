"""Tests for proposal parser."""

import json

from app.workflows.access_request.parse import parse_proposal


class TestValidJsonParses:
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


class TestPartialFieldsParse:
    def test_only_request_type_and_name(self) -> None:
        data = {"request_type": "access_request", "employee_name": "Jane Doe"}
        result = parse_proposal(json.dumps(data))
        assert result.success is True
        assert result.proposal is not None
        assert result.proposal.request_type == "access_request"
        assert result.proposal.employee_name == "Jane Doe"
        assert result.proposal.systems_requested is None
        assert result.proposal.manager_name is None


class TestExtraFieldsIgnored:
    def test_extra_field_dropped(self) -> None:
        data = {"request_type": "access_request", "extra_field": "value"}
        result = parse_proposal(json.dumps(data))
        assert result.success is True
        assert result.proposal is not None
        assert result.proposal.request_type == "access_request"
        assert not hasattr(result.proposal, "extra_field")


class TestEmptyObjectParses:
    def test_empty_json_object(self) -> None:
        result = parse_proposal("{}")
        assert result.success is True
        assert result.proposal is not None
        assert result.proposal.request_type is None
        assert result.proposal.employee_name is None


class TestMalformedJsonError:
    def test_not_json(self) -> None:
        result = parse_proposal("not json at all")
        assert result.success is False
        assert result.proposal is None
        assert result.error is not None
        assert "json" in result.error.lower() or "parse" in result.error.lower()


class TestTypeInvalidJsonError:
    def test_systems_as_string(self) -> None:
        data = {"systems_requested": "not-a-list"}
        result = parse_proposal(json.dumps(data))
        assert result.success is False
        assert result.proposal is None
        assert result.error is not None
        assert "systems_requested" in result.error
