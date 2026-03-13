"""Integration tests for policy pipeline (Feature 007, Task 002)."""

import json

from app.workflows.access_request import (
    evaluate_policy,
    normalize_proposal,
    parse_proposal,
    validate_proposal,
)
from app.workflows.access_request.reason_codes import AccessRequestReasonCode


def _run_pipeline(data: dict) -> tuple:
    """Run parse→normalize→validate→policy pipeline. Returns (parse_result, decision)."""
    parse_result = parse_proposal(json.dumps(data))
    if not parse_result.success:
        return parse_result, None

    normalized = normalize_proposal(parse_result.proposal)
    validation = validate_proposal(parse_result.proposal, normalized)
    decision = evaluate_policy(parse_result.proposal, normalized, validation)
    return parse_result, decision


class TestTask002AC1EvaluatePolicyImportable:
    """Task002 AC-1 test_evaluate_policy_importable"""

    def test_evaluate_policy_importable(self) -> None:
        from app.workflows.access_request import evaluate_policy as ep

        assert callable(ep)


class TestTask002AC2RegistryHasEvaluatePolicy:
    """Task002 AC-2 test_registry_has_evaluate_policy"""

    def test_registry_has_evaluate_policy(self) -> None:
        from app.workflows.registry import get_workflow

        module = get_workflow("access_request")
        assert callable(getattr(module, "evaluate_policy", None))


class TestTask002AC3PipelineAutoApprove:
    """Task002 AC-3 test_pipeline_auto_approve"""

    def test_pipeline_auto_approve(self) -> None:
        data = {
            "request_type": "access_request",
            "employee_name": "Jane Doe",
            "systems_requested": ["salesforce"],
            "manager_name": "Sarah Kim",
            "start_date": "2026-03-15",
            "urgency": "standard",
            "justification": "Need CRM access for onboarding",
            "recommended_action": "approve",
        }
        _, decision = _run_pipeline(data)
        assert decision is not None
        assert decision.status == "approved"
        assert decision.reason_codes == []
        assert decision.allowed_actions == ["create_simulated_approval_task"]


class TestTask002AC4PipelineReviewRequired:
    """Task002 AC-4 test_pipeline_review_required"""

    def test_pipeline_review_required(self) -> None:
        data = {
            "request_type": "access_request",
            "employee_name": "John Smith",
            "systems_requested": ["salesforce", "jira"],
            "manager_name": "Sarah Kim",
            "start_date": "2026-03-15",
            "urgency": "high",
            "justification": "Urgent project deadline",
            "recommended_action": "review",
        }
        _, decision = _run_pipeline(data)
        assert decision is not None
        assert decision.status == "review_required"
        assert AccessRequestReasonCode.HIGH_URGENCY in decision.reason_codes


class TestTask002AC5PipelineRejection:
    """Task002 AC-5 test_pipeline_rejection"""

    def test_pipeline_rejection(self) -> None:
        data = {
            "request_type": "access_request",
            "employee_name": "Jane Doe",
            "systems_requested": ["admin_console"],
            "manager_name": "Sarah Kim",
            "start_date": "2026-03-15",
            "urgency": "standard",
            "justification": "Need admin access",
            "recommended_action": "approve",
        }
        _, decision = _run_pipeline(data)
        assert decision is not None
        assert decision.status == "rejected"
        assert AccessRequestReasonCode.FORBIDDEN_SYSTEM in decision.reason_codes


class TestTask002EC1PipelineParseFailure:
    """Task002 EC-1 test_pipeline_parse_failure"""

    def test_pipeline_parse_failure(self) -> None:
        parse_result = parse_proposal("not valid json {{{")
        assert parse_result.success is False
        assert parse_result.proposal is None
        assert parse_result.error is not None


class TestTask002EC2PipelinePartialInput:
    """Task002 EC-2 test_pipeline_partial_input"""

    def test_pipeline_partial_input(self) -> None:
        data = {
            "request_type": "access_request",
            "employee_name": "Jane Doe",
        }
        _, decision = _run_pipeline(data)
        assert decision is not None
        assert decision.status == "rejected"
