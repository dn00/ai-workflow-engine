"""Integration tests for parser-validator pipeline (Feature 006, Task 006)."""

import json

import pytest

from app.workflows.access_request.reason_codes import AccessRequestReasonCode


class TestTask006AC1PipelineValidInput:
    """Task006 AC-1 test_pipeline_valid_input"""

    def test_full_pipeline_success(self) -> None:
        from app.workflows.access_request import (
            normalize_proposal,
            parse_proposal,
            validate_proposal,
        )

        data = {
            "request_type": "access_request",
            "employee_name": "Jane Doe",
            "systems_requested": ["salesforce", "looker"],
            "manager_name": "Sarah Kim",
            "start_date": "2026-03-15",
            "urgency": "standard",
            "justification": "Need access",
            "recommended_action": "approve",
        }
        parse_result = parse_proposal(json.dumps(data))
        assert parse_result.success is True
        assert parse_result.proposal is not None

        normalized = normalize_proposal(parse_result.proposal)
        assert normalized.employee_name == "Jane Doe"

        validation = validate_proposal(parse_result.proposal, normalized)
        assert validation.is_valid is True
        assert validation.errors == []


class TestTask006AC2PipelineMalformedJson:
    """Task006 AC-2 test_pipeline_malformed_json"""

    def test_malformed_json_stops_at_parse(self) -> None:
        from app.workflows.access_request import parse_proposal

        result = parse_proposal("not valid json {{{")
        assert result.success is False
        assert result.proposal is None
        assert result.error is not None


class TestTask006AC3ModuleExports:
    """Task006 AC-3 test_module_exports"""

    def test_all_functions_importable(self) -> None:
        from app.workflows.access_request import (
            normalize_proposal,
            parse_proposal,
            validate_proposal,
        )

        assert callable(parse_proposal)
        assert callable(normalize_proposal)
        assert callable(validate_proposal)


class TestTask006AC4RegistryResolvesAccessRequest:
    """Task006 AC-4 test_registry_resolves_access_request"""

    def test_get_workflow_returns_module(self) -> None:
        from app.workflows.registry import get_workflow

        module = get_workflow("access_request")
        assert module is not None
        assert module.__name__ == "app.workflows.access_request"


class TestTask006AC5ResolvedModuleHasFunctions:
    """Task006 AC-5 test_resolved_module_has_functions"""

    def test_module_has_pipeline_functions(self) -> None:
        from app.workflows.registry import get_workflow

        module = get_workflow("access_request")
        assert callable(getattr(module, "parse_proposal", None))
        assert callable(getattr(module, "normalize_proposal", None))
        assert callable(getattr(module, "validate_proposal", None))


class TestTask006EC1PipelinePartialInput:
    """Task006 EC-1 test_pipeline_partial_input"""

    def test_missing_name_and_unknown_system(self) -> None:
        from app.workflows.access_request import (
            normalize_proposal,
            parse_proposal,
            validate_proposal,
        )

        data = {
            "request_type": "access_request",
            "systems_requested": ["unknown_app"],
        }
        parse_result = parse_proposal(json.dumps(data))
        assert parse_result.success is True

        normalized = normalize_proposal(parse_result.proposal)
        assert normalized.employee_name == ""

        validation = validate_proposal(
            parse_result.proposal, normalized
        )
        assert validation.is_valid is False
        assert len(validation.errors) >= 2


class TestTask006EC2ListWorkflowTypes:
    """Task006 EC-2 test_list_workflow_types"""

    def test_returns_access_request(self) -> None:
        from app.workflows.registry import list_workflow_types

        types = list_workflow_types()
        assert "access_request" in types


class TestTask006ERR1PipelineForbiddenSystem:
    """Task006 ERR-1 test_pipeline_forbidden_system"""

    def test_forbidden_system_detected(self) -> None:
        from app.workflows.access_request import (
            normalize_proposal,
            parse_proposal,
            validate_proposal,
        )

        data = {
            "request_type": "access_request",
            "employee_name": "Jane Doe",
            "systems_requested": ["admin_console"],
            "start_date": "2026-03-15",
        }
        parse_result = parse_proposal(json.dumps(data))
        assert parse_result.success is True

        normalized = normalize_proposal(parse_result.proposal)
        assert normalized.systems_requested == ["admin_console"]

        validation = validate_proposal(
            parse_result.proposal, normalized
        )
        assert validation.is_valid is False
        assert (
            AccessRequestReasonCode.FORBIDDEN_SYSTEM
            in validation.errors
        )


class TestTask006ERR2UnknownWorkflowRaises:
    """Task006 ERR-2 test_unknown_workflow_raises"""

    def test_nonexistent_raises_valueerror(self) -> None:
        from app.workflows.registry import get_workflow

        with pytest.raises(
            ValueError, match="Unknown workflow type"
        ):
            get_workflow("nonexistent_workflow")
