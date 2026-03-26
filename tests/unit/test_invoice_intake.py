"""Tests for the invoice_intake workflow — parsing, validation, and policy."""

import json

import pytest

from app.workflows.invoice_intake.parse import parse_proposal
from app.workflows.invoice_intake.normalize import normalize_proposal
from app.workflows.invoice_intake.validate import validate_proposal
from app.workflows.invoice_intake.policy import evaluate_policy
from app.workflows.invoice_intake.allowlist import classify_vendor


# -- Parsing -------------------------------------------------------------------


class TestInvoiceParser:
    def test_valid_invoice_parses(self):
        raw = json.dumps({
            "request_type": "invoice_intake",
            "vendor_name": "Acme Corp",
            "invoice_number": "INV-2026-001",
            "total": 1500.00,
            "line_items": [{"description": "Widgets", "quantity": 10, "unit_price": 150, "amount": 1500}],
        })
        result = parse_proposal(raw)
        assert result.success
        assert result.proposal.vendor_name == "Acme Corp"
        assert len(result.proposal.line_items) == 1

    def test_strips_markdown_fences(self):
        raw = '```json\n{"request_type": "invoice_intake", "vendor_name": "X", "total": 100}\n```'
        result = parse_proposal(raw)
        assert result.success

    def test_malformed_json_fails(self):
        result = parse_proposal("not json")
        assert not result.success


# -- Allowlist -----------------------------------------------------------------


class TestVendorAllowlist:
    @pytest.mark.parametrize("name", ["acme corp", "aws", "snowflake", "datadog"])
    def test_known_vendors(self, name):
        assert classify_vendor(name) == "known"

    def test_flagged_vendor(self):
        assert classify_vendor("offshore consulting ltd") == "flagged"

    def test_unknown_vendor(self):
        assert classify_vendor("random vendor xyz") == "unknown"

    def test_case_insensitive(self):
        assert classify_vendor("ACME CORP") == "known"


# -- Validation ----------------------------------------------------------------


class TestInvoiceValidator:
    def _parse_and_normalize(self, **overrides):
        base = {
            "request_type": "invoice_intake",
            "vendor_name": "Acme Corp",
            "invoice_number": "INV-001",
            "total": 1500.00,
            "line_items": [{"description": "Service", "amount": 1500.00}],
        }
        base.update(overrides)
        result = parse_proposal(json.dumps(base))
        assert result.success
        return result.proposal, normalize_proposal(result.proposal)

    def test_valid_invoice_passes(self):
        proposal, normalized = self._parse_and_normalize()
        result = validate_proposal(proposal, normalized)
        assert result.is_valid

    def test_missing_vendor_rejected(self):
        proposal, normalized = self._parse_and_normalize(vendor_name=None)
        result = validate_proposal(proposal, normalized)
        assert not result.is_valid
        assert "missing_vendor_name" in result.errors

    def test_missing_invoice_number_rejected(self):
        proposal, normalized = self._parse_and_normalize(invoice_number=None)
        result = validate_proposal(proposal, normalized)
        assert not result.is_valid
        assert "missing_invoice_number" in result.errors

    def test_flagged_vendor_rejected(self):
        proposal, normalized = self._parse_and_normalize(vendor_name="Offshore Consulting Ltd")
        result = validate_proposal(proposal, normalized)
        assert not result.is_valid
        assert "flagged_vendor" in result.errors

    def test_zero_total_rejected(self):
        proposal, normalized = self._parse_and_normalize(total=0)
        result = validate_proposal(proposal, normalized)
        assert not result.is_valid
        assert "invalid_total" in result.errors

    def test_bad_date_rejected(self):
        proposal, normalized = self._parse_and_normalize(invoice_date="not-a-date")
        result = validate_proposal(proposal, normalized)
        assert not result.is_valid
        assert "malformed_date" in result.errors

    def test_wrong_request_type(self):
        proposal, normalized = self._parse_and_normalize(request_type="access_request")
        result = validate_proposal(proposal, normalized)
        assert not result.is_valid


# -- Policy --------------------------------------------------------------------


class TestInvoicePolicy:
    def _run_policy(self, **overrides):
        base = {
            "request_type": "invoice_intake",
            "vendor_name": "Acme Corp",
            "invoice_number": "INV-001",
            "total": 1500.00,
            "line_items": [{"description": "Service", "amount": 1500.00}],
        }
        base.update(overrides)
        result = parse_proposal(json.dumps(base))
        assert result.success
        normalized = normalize_proposal(result.proposal)
        vr = validate_proposal(result.proposal, normalized)
        return evaluate_policy(result.proposal, normalized, vr)

    def test_small_known_vendor_auto_approved(self):
        decision = self._run_policy(total=500.00, line_items=[{"description": "X", "amount": 500}])
        assert decision.status == "approved"

    def test_large_invoice_triggers_review(self):
        decision = self._run_policy(total=10000.00, line_items=[{"description": "X", "amount": 10000}])
        assert decision.status == "review_required"
        assert "above_auto_approve_threshold" in decision.reason_codes

    def test_very_large_invoice_triggers_review(self):
        decision = self._run_policy(total=75000.00, line_items=[{"description": "X", "amount": 75000}])
        assert decision.status == "review_required"
        assert "high_value_invoice" in decision.reason_codes

    def test_unknown_vendor_triggers_review(self):
        decision = self._run_policy(vendor_name="Random Vendor")
        assert decision.status == "review_required"
        assert "unknown_vendor" in decision.reason_codes

    def test_line_item_mismatch_triggers_review(self):
        decision = self._run_policy(
            total=1500.00,
            line_items=[{"description": "X", "amount": 1000.00}],  # doesn't add up
        )
        assert decision.status == "review_required"
        assert "line_item_total_mismatch" in decision.reason_codes

    def test_no_line_items_triggers_review(self):
        decision = self._run_policy(line_items=[])
        assert decision.status == "review_required"
        assert "no_line_items" in decision.reason_codes

    def test_flagged_vendor_rejected(self):
        decision = self._run_policy(vendor_name="Offshore Consulting Ltd")
        assert decision.status == "rejected"
