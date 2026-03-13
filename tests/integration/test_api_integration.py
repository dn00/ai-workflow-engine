"""Cross-endpoint integration tests exercising full API flows for all demo scenarios.

Feature 014, Batch 03, Task 004.
Tests use TestClient + create_app with in-memory SQLite and configured MockLLMAdapter.
"""

import json

import pytest
from starlette.testclient import TestClient

from app.llm.mock_adapter import MockLLMAdapter
from app.main import create_app

# ---------------------------------------------------------------------------
# Fixtures — human-readable input strings mapped to fixture JSON responses
# ---------------------------------------------------------------------------

HAPPY_PATH_INPUT = "Happy path: one system, standard urgency"
REVIEW_PATH_INPUT = "Review path: multiple systems, high urgency"
REJECTION_PATH_INPUT = "Rejection path: forbidden admin system"

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
    })
    app = create_app(db_url="sqlite:///:memory:", llm_adapter=adapter)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Task004 AC-1: Demo 1 — happy path via API
# ---------------------------------------------------------------------------


def test_demo_1_happy_path_via_api(client: TestClient):
    """Task004 AC-1 test_demo_1_happy_path_via_api"""
    # POST /runs — create a run
    create_resp = client.post(
        "/runs", json={"input_text": HAPPY_PATH_INPUT, "mode": "live"}
    )
    assert create_resp.status_code == 201
    run_id = create_resp.json()["run"]["run_id"]
    assert create_resp.json()["run"]["status"] == "completed"
    assert create_resp.json()["projection"] is not None

    # GET /runs/{id} — verify run summary
    get_resp = client.get(f"/runs/{run_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "completed"
    assert get_resp.json()["current_projection"] is not None

    # GET /runs/{id}/events — verify events include effect.simulated
    events_resp = client.get(f"/runs/{run_id}/events")
    assert events_resp.status_code == 200
    event_types = [e["event_type"] for e in events_resp.json()["events"]]
    assert "effect.simulated" in event_types
    assert "run.completed" in event_types


# ---------------------------------------------------------------------------
# Task004 AC-2: Demo 2 — review path via API
# ---------------------------------------------------------------------------


def test_demo_2_review_path_via_api(client: TestClient):
    """Task004 AC-2 test_demo_2_review_path_via_api"""
    # POST /runs — create run that needs review
    create_resp = client.post(
        "/runs", json={"input_text": REVIEW_PATH_INPUT, "mode": "live"}
    )
    assert create_resp.status_code == 201
    run_id = create_resp.json()["run"]["run_id"]
    assert create_resp.json()["run"]["status"] == "review_required"
    assert create_resp.json()["review_task"] is not None

    # GET /runs/{id} — verify review_required
    get_resp = client.get(f"/runs/{run_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "review_required"

    # POST /runs/{id}/review — approve
    review_resp = client.post(
        f"/runs/{run_id}/review", json={"decision": "approve"}
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["run"]["status"] == "completed"
    assert review_resp.json()["review_task"] is not None

    # GET /runs/{id} — verify completed after review
    get_resp2 = client.get(f"/runs/{run_id}")
    assert get_resp2.status_code == 200
    assert get_resp2.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# Task004 AC-3: Demo 3 — rejection path via API
# ---------------------------------------------------------------------------


def test_demo_3_rejection_via_api(client: TestClient):
    """Task004 AC-3 test_demo_3_rejection_via_api"""
    # POST /runs with forbidden system — triggers validation failure
    create_resp = client.post(
        "/runs", json={"input_text": REJECTION_PATH_INPUT, "mode": "live"}
    )
    assert create_resp.status_code == 201
    run_id = create_resp.json()["run"]["run_id"]

    # GET /runs/{id} — verify terminal state (not auto-approved)
    get_resp = client.get(f"/runs/{run_id}")
    assert get_resp.status_code == 200
    run_status = get_resp.json()["status"]
    assert run_status != "review_required"  # not pending review

    # GET /runs/{id}/events — verify no effect events
    events_resp = client.get(f"/runs/{run_id}/events")
    assert events_resp.status_code == 200
    event_types = [e["event_type"] for e in events_resp.json()["events"]]
    assert "effect.requested" not in event_types
    assert "effect.simulated" not in event_types


# ---------------------------------------------------------------------------
# Task004 AC-4: Demo 4 — replay via API
# ---------------------------------------------------------------------------


def test_demo_4_replay_via_api(client: TestClient):
    """Task004 AC-4 test_demo_4_replay_via_api"""
    # Create a completed run first
    create_resp = client.post(
        "/runs", json={"input_text": HAPPY_PATH_INPUT, "mode": "live"}
    )
    assert create_resp.status_code == 201
    run_id = create_resp.json()["run"]["run_id"]
    assert create_resp.json()["run"]["status"] == "completed"

    # POST /runs/{id}/replay
    replay_resp = client.post(f"/runs/{run_id}/replay")
    assert replay_resp.status_code == 200
    data = replay_resp.json()
    assert data["run_id"] == run_id
    assert data["match"] is True
    assert data["replayed_projection"] is not None
    assert data["stored_projection"] is not None


# ---------------------------------------------------------------------------
# Task004 EC-1: Events accumulate across API calls
# ---------------------------------------------------------------------------


def test_events_accumulate(client: TestClient):
    """Task004 EC-1 test_events_accumulate"""
    # Create a happy-path run (produces 7 events for live auto-approve)
    create_resp = client.post(
        "/runs", json={"input_text": HAPPY_PATH_INPUT, "mode": "live"}
    )
    run_id = create_resp.json()["run"]["run_id"]

    # GET events
    events_resp = client.get(f"/runs/{run_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()["events"]

    # Should have >=5 events
    assert len(events) >= 5

    # Sequential seq values starting at 1
    seqs = [e["seq"] for e in events]
    assert seqs[0] == 1
    assert seqs == list(range(1, len(seqs) + 1))


# ---------------------------------------------------------------------------
# Task004 ERR-1: Review on completed (non-review_required) run returns 409
# ---------------------------------------------------------------------------


def test_review_on_completed_run_409(client: TestClient):
    """Task004 ERR-1 test_review_on_completed_run_409"""
    # Create a happy-path run (auto-approved, status=completed)
    create_resp = client.post(
        "/runs", json={"input_text": HAPPY_PATH_INPUT, "mode": "live"}
    )
    run_id = create_resp.json()["run"]["run_id"]
    assert create_resp.json()["run"]["status"] == "completed"

    # Attempt review on completed run
    review_resp = client.post(
        f"/runs/{run_id}/review", json={"decision": "approve"}
    )
    assert review_resp.status_code == 409
    assert "not in review_required status" in review_resp.json()["detail"]
