"""Integration tests for the invoice_intake workflow through the API."""

import json

import pytest
from starlette.testclient import TestClient

from app.llm.mock_adapter import MockLLMAdapter
from app.main import create_app

SMALL_INVOICE_INPUT = "small invoice from known vendor"
LARGE_INVOICE_INPUT = "large invoice needs review"
FLAGGED_VENDOR_INPUT = "invoice from flagged vendor"

SMALL_INVOICE_JSON = json.dumps({
    "request_type": "invoice_intake",
    "vendor_name": "Acme Corp",
    "invoice_number": "INV-2026-042",
    "invoice_date": "2026-03-15",
    "due_date": "2026-04-14",
    "currency": "USD",
    "line_items": [
        {"description": "Consulting services", "quantity": 10, "unit_price": 200, "amount": 2000},
        {"description": "Travel expenses", "quantity": 1, "unit_price": 500, "amount": 500},
    ],
    "subtotal": 2500,
    "tax": 0,
    "total": 2500,
    "payment_terms": "Net 30",
    "notes": [],
})

LARGE_INVOICE_JSON = json.dumps({
    "request_type": "invoice_intake",
    "vendor_name": "Snowflake",
    "invoice_number": "SNO-88821",
    "invoice_date": "2026-03-01",
    "due_date": "2026-03-31",
    "currency": "USD",
    "line_items": [
        {"description": "Compute credits", "amount": 35000},
        {"description": "Storage", "amount": 15000},
    ],
    "subtotal": 50000,
    "tax": 5000,
    "total": 55000,
    "notes": [],
})

FLAGGED_VENDOR_JSON = json.dumps({
    "request_type": "invoice_intake",
    "vendor_name": "Offshore Consulting Ltd",
    "invoice_number": "OFF-001",
    "total": 9999,
    "line_items": [{"description": "Services", "amount": 9999}],
})


@pytest.fixture
def invoice_client():
    adapter = MockLLMAdapter(responses={
        SMALL_INVOICE_INPUT: SMALL_INVOICE_JSON,
        LARGE_INVOICE_INPUT: LARGE_INVOICE_JSON,
        FLAGGED_VENDOR_INPUT: FLAGGED_VENDOR_JSON,
    })
    app = create_app(db_url="sqlite:///:memory:", llm_adapter=adapter)
    with TestClient(app) as c:
        yield c


def test_small_invoice_auto_approved(invoice_client):
    resp = invoice_client.post("/runs", json={
        "input_text": SMALL_INVOICE_INPUT,
        "mode": "live",
        "workflow_type": "invoice_intake",
    })
    assert resp.status_code == 201
    assert resp.json()["run"]["status"] == "completed"
    types = [
        e["event_type"]
        for e in invoice_client.get(f"/runs/{resp.json()['run']['run_id']}/events").json()["events"]
    ]
    assert "effect.simulated" in types


def test_large_invoice_needs_review(invoice_client):
    resp = invoice_client.post("/runs", json={
        "input_text": LARGE_INVOICE_INPUT,
        "mode": "live",
        "workflow_type": "invoice_intake",
    })
    assert resp.status_code == 201
    assert resp.json()["run"]["status"] == "review_required"

    run_id = resp.json()["run"]["run_id"]
    review = invoice_client.post(f"/runs/{run_id}/review", json={"decision": "approve"})
    assert review.json()["run"]["status"] == "completed"


def test_flagged_vendor_rejected(invoice_client):
    resp = invoice_client.post("/runs", json={
        "input_text": FLAGGED_VENDOR_INPUT,
        "mode": "live",
        "workflow_type": "invoice_intake",
    })
    assert resp.status_code == 201
    status = resp.json()["run"]["status"]
    assert status in ("proposal_invalid", "completed")

    run_id = resp.json()["run"]["run_id"]
    types = [
        e["event_type"]
        for e in invoice_client.get(f"/runs/{run_id}/events").json()["events"]
    ]
    assert "effect.simulated" not in types


def test_invoice_replay_matches(invoice_client):
    resp = invoice_client.post("/runs", json={
        "input_text": SMALL_INVOICE_INPUT,
        "mode": "live",
        "workflow_type": "invoice_intake",
    })
    run_id = resp.json()["run"]["run_id"]

    replay = invoice_client.post(f"/runs/{run_id}/replay")
    assert replay.status_code == 200
    assert replay.json()["match"] is True
