"""Tests for invoice_exception parsing, normalization, validation, and policy."""

import json

import pytest

from app.workflows.invoice_exception.allowlist import classify_vendor
from app.workflows.invoice_exception.normalize import normalize_proposal
from app.workflows.invoice_exception.parse import parse_proposal
from app.workflows.invoice_exception.policy import evaluate_policy
from app.workflows.invoice_exception.prompt import build_user_prompt
from app.workflows.invoice_exception.retrieval import (
    build_policy_query,
    build_retrieval_query,
)
from app.workflows.invoice_exception.validate import validate_proposal


def _proposal_json(**overrides) -> str:
    data = {
        "request_type": "invoice_exception",
        "vendor_name": "Acme Corp",
        "invoice_number": "INV-1042",
        "po_number": "PO-9001",
        "invoice_amount": 18750.0,
        "po_amount": 15000.0,
        "currency": "usd",
        "discrepancy_reason": "Expedited shipping and weekend labor.",
        "line_items": [
            {"description": "Base services", "amount": 15000.0},
            {"description": "Expedited shipping", "amount": 2500.0},
            {"description": "Weekend labor", "amount": 1250.0},
        ],
        "cited_evidence_ids": [
            "invoice_overage_policy:0:abc",
            "vendor_surcharge_policy:0:def",
        ],
        "notes": [],
    }
    data.update(overrides)
    return json.dumps(data)


def _decision(**overrides):
    result = parse_proposal(_proposal_json(**overrides))
    assert result.success
    normalized = normalize_proposal(result.proposal)
    validation = validate_proposal(result.proposal, normalized)
    return evaluate_policy(result.proposal, normalized, validation)


class TestInvoiceExceptionParser:
    def test_valid_exception_parses(self) -> None:
        result = parse_proposal(_proposal_json())

        assert result.success is True
        assert result.proposal.vendor_name == "Acme Corp"
        assert result.proposal.invoice_amount == 18750.0

    def test_strips_markdown_fences(self) -> None:
        result = parse_proposal(f"```json\n{_proposal_json()}\n```")

        assert result.success is True

    def test_malformed_json_fails(self) -> None:
        result = parse_proposal("not json")

        assert result.success is False
        assert "JSON parse error" in result.error


class TestInvoiceExceptionNormalization:
    def test_computes_overage_fields_and_review_packet(self) -> None:
        result = parse_proposal(_proposal_json())
        normalized = normalize_proposal(result.proposal)

        assert normalized.currency == "USD"
        assert normalized.overage_amount == 3750.0
        assert normalized.overage_percent == 25.0
        assert "INV-1042" in normalized.review_packet.summary
        assert normalized.review_packet.cited_evidence_ids == [
            "invoice_overage_policy:0:abc",
            "vendor_surcharge_policy:0:def",
        ]


class TestInvoiceExceptionValidation:
    def test_valid_exception_passes(self) -> None:
        result = parse_proposal(_proposal_json())
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is True

    @pytest.mark.parametrize(
        ("field", "value", "error"),
        [
            ("vendor_name", None, "missing_vendor_name"),
            ("invoice_number", None, "missing_invoice_number"),
            ("po_number", None, "missing_po_number"),
            ("invoice_amount", 0, "invalid_invoice_amount"),
            ("po_amount", 0, "invalid_po_amount"),
            ("discrepancy_reason", "", "missing_discrepancy_reason"),
        ],
    )
    def test_required_fields(self, field: str, value, error: str) -> None:
        result = parse_proposal(_proposal_json(**{field: value}))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert error in validation.errors

    def test_flagged_vendor_is_valid_for_policy_rejection(self) -> None:
        result = parse_proposal(
            _proposal_json(vendor_name="Offshore Consulting Ltd")
        )
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is True
        assert "flagged_vendor" not in validation.errors


class TestInvoiceExceptionPolicy:
    def test_known_vendor_surcharge_overage_requires_review(self) -> None:
        decision = _decision()

        assert decision.status == "review_required"
        assert "po_amount_exceeded" in decision.reason_codes
        assert "unsupported_surcharge" in decision.reason_codes
        assert "manager_approval_required" in decision.reason_codes

    def test_large_overage_requires_director_review(self) -> None:
        decision = _decision(invoice_amount=20000.0, po_amount=10000.0)

        assert decision.status == "review_required"
        assert "director_approval_required" in decision.reason_codes

    def test_minor_overage_with_evidence_can_auto_approve(self) -> None:
        decision = _decision(
            invoice_amount=1030.0,
            po_amount=1000.0,
            discrepancy_reason="Small tax rounding adjustment.",
            line_items=[{"description": "Tax rounding", "amount": 30.0}],
            cited_evidence_ids=["invoice_overage_policy:0:abc"],
        )

        assert decision.status == "approved"
        assert decision.reason_codes == ["minor_overage_with_evidence"]

    def test_missing_citations_requires_review(self) -> None:
        decision = _decision(
            discrepancy_reason="Small tax rounding adjustment.",
            line_items=[{"description": "Tax rounding", "amount": 30.0}],
            cited_evidence_ids=[],
        )

        assert decision.status == "review_required"
        assert "missing_evidence_citations" in decision.reason_codes

    def test_validation_errors_reject(self) -> None:
        decision = _decision(invoice_number=None)

        assert decision.status == "rejected"
        assert "missing_invoice_number" in decision.reason_codes

    def test_flagged_vendor_rejects_in_policy(self) -> None:
        decision = _decision(vendor_name="Offshore Consulting Ltd")

        assert decision.status == "rejected"
        assert decision.reason_codes == ["flagged_vendor"]


class TestInvoiceExceptionHelpers:
    def test_vendor_classification(self) -> None:
        assert classify_vendor("Acme") == "known"
        assert classify_vendor("Offshore Consulting Ltd") == "flagged"
        assert classify_vendor("Unknown Vendor") == "unknown"

    def test_prompt_accepts_retrieved_context(self) -> None:
        prompt = build_user_prompt("Review invoice INV-1", "[policy:0] Source: x")

        assert "Review invoice INV-1" in prompt
        assert "[policy:0] Source: x" in prompt

    def test_retrieval_query_helpers_include_domain_terms(self) -> None:
        result = parse_proposal(_proposal_json())
        normalized = normalize_proposal(result.proposal)

        assert "invoice exception" in build_retrieval_query("Acme overage")
        assert "Acme Corp" in build_policy_query(result.proposal, normalized)
