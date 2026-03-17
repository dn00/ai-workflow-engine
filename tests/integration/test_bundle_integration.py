"""Integration tests for GET /runs/{run_id}/bundle — end-to-end bundle export.
Tests use TestClient + create_app with in-memory SQLite and configured MockLLMAdapter.
"""

import json

import pytest
from starlette.testclient import TestClient

from app.llm.mock_adapter import MockLLMAdapter
from app.main import create_app

# ---------------------------------------------------------------------------
# Fixtures — reuse same fixture data as test_api_integration.py
# ---------------------------------------------------------------------------

HAPPY_PATH_INPUT = "Happy path: one system, standard urgency"
REVIEW_PATH_INPUT = "Review path: multiple systems, high urgency"
REJECTION_PATH_INPUT = "Rejection path: forbidden admin system"

# Will produce parse failure - not valid JSON
PARSE_FAILURE_INPUT = "Parse failure: invalid response"

HAPPY_PATH_JSON = json.dumps({
    "request_type": "access_request",
    "employee_name": "Jane Doe",
    "systems_requested": ["salesforce"],
    "manager_name": "Sarah Kim",
    "start_date": "2026-03-15",
    "urgency": "standard",
    "justification": "Need CRM access for onboarding",
})

REVIEW_REQUIRED_JSON = json.dumps({
    "request_type": "access_request",
    "employee_name": "John Smith",
    "systems_requested": ["salesforce", "jira"],
    "manager_name": "Sarah Kim",
    "urgency": "high",
    "justification": "Urgent project deadline",
})

FORBIDDEN_SYSTEM_JSON = json.dumps({
    "request_type": "access_request",
    "employee_name": "Jane Doe",
    "systems_requested": ["admin_console"],
    "manager_name": "Sarah Kim",
})


@pytest.fixture
def client():
    adapter = MockLLMAdapter(responses={
        HAPPY_PATH_INPUT: HAPPY_PATH_JSON,
        REVIEW_PATH_INPUT: REVIEW_REQUIRED_JSON,
        REJECTION_PATH_INPUT: FORBIDDEN_SYSTEM_JSON,
        PARSE_FAILURE_INPUT: "NOT VALID JSON {{{",
    })
    app = create_app(db_url="sqlite:///:memory:", llm_adapter=adapter)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# test_bundle_approved_run_end_to_end
# ---------------------------------------------------------------------------


class TestBundleApprovedRunEndToEnd:
    def test_bundle_approved_run_end_to_end(self, client: TestClient):
        # Create a happy-path auto-approved run
        create_resp = client.post(
            "/runs", json={"input_text": HAPPY_PATH_INPUT, "mode": "live"}
        )
        assert create_resp.status_code == 201
        run_id = create_resp.json()["run"]["run_id"]
        assert create_resp.json()["run"]["status"] == "completed"

        # Export bundle
        bundle_resp = client.get(f"/runs/{run_id}/bundle")
        assert bundle_resp.status_code == 200
        data = bundle_resp.json()

        # Bundle metadata
        assert data["bundle_version"] == "1.0"
        assert "exported_at" in data

        # Run
        assert data["run"]["run_id"] == run_id
        assert data["run"]["status"] == "completed"

        # Events ordered by seq
        events = data["events"]
        assert len(events) >= 5
        seqs = [e["seq"] for e in events]
        assert seqs == sorted(seqs)
        assert seqs[0] == 1

        # Receipt present
        assert data["receipt"] is not None
        assert data["receipt"]["raw_response"] is not None

        # Projection present
        assert data["projection"] is not None


# ---------------------------------------------------------------------------
# test_bundle_rejected_run_end_to_end
# ---------------------------------------------------------------------------


class TestBundleRejectedRunEndToEnd:
    def test_bundle_rejected_run_end_to_end(self, client: TestClient):
        # Create a rejection-path run (forbidden system → validation failure)
        create_resp = client.post(
            "/runs", json={"input_text": REJECTION_PATH_INPUT, "mode": "live"}
        )
        assert create_resp.status_code == 201
        run_id = create_resp.json()["run"]["run_id"]

        # Export bundle
        bundle_resp = client.get(f"/runs/{run_id}/bundle")
        assert bundle_resp.status_code == 200
        data = bundle_resp.json()

        # Run reached terminal state (proposal_invalid for forbidden system)
        assert data["run"]["status"] in ("completed", "proposal_invalid")

        # Events reflect rejection path — no effect events
        event_types = [e["event_type"] for e in data["events"]]
        assert "effect.requested" not in event_types
        assert "effect.simulated" not in event_types

        # Receipt present
        assert data["receipt"] is not None


# ---------------------------------------------------------------------------
# test_bundle_proposal_invalid_run
# ---------------------------------------------------------------------------


class TestBundleProposalInvalidRun:
    def test_bundle_proposal_invalid_run(self, client: TestClient):
        # Create a parse failure run
        create_resp = client.post(
            "/runs", json={"input_text": PARSE_FAILURE_INPUT, "mode": "live"}
        )
        assert create_resp.status_code == 201
        run_id = create_resp.json()["run"]["run_id"]

        # Export bundle
        bundle_resp = client.get(f"/runs/{run_id}/bundle")
        assert bundle_resp.status_code == 200
        data = bundle_resp.json()

        # Events include parse failure
        event_types = [e["event_type"] for e in data["events"]]
        assert "run.received" in event_types
        assert "proposal.parse_failed" in event_types

        # Receipt present (INV-1.2: stored before parsing)
        assert data["receipt"] is not None

        # Projection reflects proposal_invalid
        assert data["projection"] is not None


# ---------------------------------------------------------------------------
# test_bundle_in_progress_run
# ---------------------------------------------------------------------------


class TestBundleInProgressRun:
    def test_bundle_in_progress_run(self, client: TestClient):
        # Create a review-required run (paused state)
        create_resp = client.post(
            "/runs", json={"input_text": REVIEW_PATH_INPUT, "mode": "live"}
        )
        assert create_resp.status_code == 201
        run_id = create_resp.json()["run"]["run_id"]
        assert create_resp.json()["run"]["status"] == "review_required"

        # Export bundle for in-progress run
        bundle_resp = client.get(f"/runs/{run_id}/bundle")
        assert bundle_resp.status_code == 200
        data = bundle_resp.json()

        # Run is still in review_required state
        assert data["run"]["status"] == "review_required"

        # Events up to review.requested
        event_types = [e["event_type"] for e in data["events"]]
        assert "run.received" in event_types
        assert "review.requested" in event_types

        # Receipt present
        assert data["receipt"] is not None

        # Projection reflects current state
        assert data["projection"] is not None
