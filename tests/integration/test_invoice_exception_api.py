"""Integration tests for the invoice_exception workflow through the API."""

import json

import pytest
from starlette.testclient import TestClient

from app.llm.mock_adapter import MockLLMAdapter
from app.main import create_app

EXCEPTION_REVIEW_INPUT = "Acme invoice exceeds PO with expedited shipping."
MINOR_OVERAGE_INPUT = "Acme invoice has a small rounding overage."
FLAGGED_VENDOR_INPUT = "Invoice exception from flagged vendor."

EXCEPTION_REVIEW_JSON = json.dumps(
    {
        "request_type": "invoice_exception",
        "vendor_name": "Acme Corp",
        "invoice_number": "INV-1042",
        "po_number": "PO-9001",
        "invoice_amount": 18750.0,
        "po_amount": 15000.0,
        "currency": "USD",
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
)

MINOR_OVERAGE_JSON = json.dumps(
    {
        "request_type": "invoice_exception",
        "vendor_name": "Acme Corp",
        "invoice_number": "INV-1001",
        "po_number": "PO-1001",
        "invoice_amount": 1030.0,
        "po_amount": 1000.0,
        "currency": "USD",
        "discrepancy_reason": "Small tax rounding adjustment.",
        "line_items": [{"description": "Tax rounding", "amount": 30.0}],
        "cited_evidence_ids": ["invoice_overage_policy:0:abc"],
        "notes": [],
    }
)

FLAGGED_VENDOR_JSON = json.dumps(
    {
        "request_type": "invoice_exception",
        "vendor_name": "Offshore Consulting Ltd",
        "invoice_number": "OFF-404",
        "po_number": "PO-404",
        "invoice_amount": 9000.0,
        "po_amount": 8000.0,
        "currency": "USD",
        "discrepancy_reason": "Extra services.",
        "line_items": [{"description": "Extra services", "amount": 1000.0}],
        "cited_evidence_ids": ["ap_approval_policy:0:abc"],
        "notes": [],
    }
)


@pytest.fixture
def invoice_exception_client():
    adapter = MockLLMAdapter(
        responses={
            EXCEPTION_REVIEW_INPUT: EXCEPTION_REVIEW_JSON,
            MINOR_OVERAGE_INPUT: MINOR_OVERAGE_JSON,
            FLAGGED_VENDOR_INPUT: FLAGGED_VENDOR_JSON,
        }
    )
    app = create_app(db_url="sqlite:///:memory:", llm_adapter=adapter)
    with TestClient(app) as client:
        yield client


def test_invoice_exception_routes_to_review(invoice_exception_client) -> None:
    response = invoice_exception_client.post(
        "/runs",
        json={
            "input_text": EXCEPTION_REVIEW_INPUT,
            "mode": "live",
            "workflow_type": "invoice_exception",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["run"]["workflow_type"] == "invoice_exception"
    assert body["run"]["status"] == "review_required"
    assert body["review_task"] is not None


def test_invoice_exception_bundle_includes_artifacts(invoice_exception_client) -> None:
    response = invoice_exception_client.post(
        "/runs",
        json={
            "input_text": EXCEPTION_REVIEW_INPUT,
            "mode": "live",
            "workflow_type": "invoice_exception",
        },
    )
    run_id = response.json()["run"]["run_id"]

    bundle = invoice_exception_client.get(f"/runs/{run_id}/bundle")

    assert bundle.status_code == 200
    artifact_types = {
        artifact["artifact_type"] for artifact in bundle.json()["artifacts"]
    }
    assert "invoice_exception.proposal" in artifact_types
    assert "invoice_exception.normalized" in artifact_types


def test_minor_invoice_exception_can_complete(invoice_exception_client) -> None:
    response = invoice_exception_client.post(
        "/runs",
        json={
            "input_text": MINOR_OVERAGE_INPUT,
            "mode": "live",
            "workflow_type": "invoice_exception",
        },
    )

    assert response.status_code == 201
    assert response.json()["run"]["status"] == "completed"


def test_flagged_vendor_rejects_through_api(invoice_exception_client) -> None:
    response = invoice_exception_client.post(
        "/runs",
        json={
            "input_text": FLAGGED_VENDOR_INPUT,
            "mode": "live",
            "workflow_type": "invoice_exception",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["run"]["status"] == "completed"
    assert body["projection"]["policy_decision"]["status"] == "rejected"
    assert "flagged_vendor" in body["projection"]["policy_decision"]["reason_codes"]
