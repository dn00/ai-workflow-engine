"""Tests for action endpoints: POST /runs/{run_id}/review, POST /runs/{run_id}/replay.

Feature 014, Batch 02, Task 003.
"""

import json

import pytest
from starlette.testclient import TestClient

from app.llm.mock_adapter import MockLLMAdapter
from app.main import create_app

# ---------------------------------------------------------------------------
# Fixtures — same JSON values as integration tests
# ---------------------------------------------------------------------------

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


@pytest.fixture
def client():
    llm_adapter = MockLLMAdapter(responses={
        HAPPY_PATH_JSON: HAPPY_PATH_JSON,
        REVIEW_REQUIRED_JSON: REVIEW_REQUIRED_JSON,
    })
    app = create_app("sqlite:///:memory:", llm_adapter=llm_adapter)
    with TestClient(app) as c:
        yield c


def _create_review_run(client: TestClient) -> str:
    """Helper: create a run that ends in review_required status."""
    resp = client.post("/runs", json={"input_text": REVIEW_REQUIRED_JSON, "mode": "live"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["run"]["status"] == "review_required"
    return data["run"]["run_id"]


def _create_completed_run(client: TestClient) -> str:
    """Helper: create a run that completes via happy path."""
    resp = client.post("/runs", json={"input_text": HAPPY_PATH_JSON, "mode": "live"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["run"]["status"] == "completed"
    return data["run"]["run_id"]


# ---------------------------------------------------------------------------
# Task003 AC-1: POST /runs/{run_id}/review approves a pending run
# ---------------------------------------------------------------------------


def test_review_approve(client: TestClient):
    """Task003 AC-1 test_review_approve"""
    run_id = _create_review_run(client)

    resp = client.post(f"/runs/{run_id}/review", json={"decision": "approve"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["run"]["status"] == "completed"
    assert data["projection"]["review_decision"] == "approve"


# ---------------------------------------------------------------------------
# Task003 AC-2: POST /runs/{run_id}/review rejects a pending run
# ---------------------------------------------------------------------------


def test_review_reject(client: TestClient):
    """Task003 AC-2 test_review_reject"""
    run_id = _create_review_run(client)

    resp = client.post(f"/runs/{run_id}/review", json={"decision": "reject"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["run"]["status"] == "completed"
    assert data["projection"]["review_decision"] == "reject"


# ---------------------------------------------------------------------------
# Task003 AC-3: POST /runs/{run_id}/replay returns replay result
# ---------------------------------------------------------------------------


def test_replay_run(client: TestClient):
    """Task003 AC-3 test_replay_run"""
    run_id = _create_completed_run(client)

    resp = client.post(f"/runs/{run_id}/replay")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert "match" in data
    assert "replayed_projection" in data
    assert "stored_projection" in data
    assert "event_count" in data


# ---------------------------------------------------------------------------
# Task003 EC-1: Replay on completed run with matching projection
# ---------------------------------------------------------------------------


def test_replay_completed_run_match(client: TestClient):
    """Task003 EC-1 test_replay_completed_run_match"""
    run_id = _create_completed_run(client)

    resp = client.post(f"/runs/{run_id}/replay")
    assert resp.status_code == 200
    data = resp.json()
    assert data["match"] is True
    assert data["replayed_projection"] is not None
    assert data["stored_projection"] is not None


# ---------------------------------------------------------------------------
# Task003 EC-2: Review response includes review_task
# ---------------------------------------------------------------------------


def test_review_response_includes_review_task(client: TestClient):
    """Task003 EC-2 test_review_response_includes_review_task"""
    run_id = _create_review_run(client)

    resp = client.post(f"/runs/{run_id}/review", json={"decision": "approve"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_task"] is not None
    assert "review_id" in data["review_task"]
    assert data["review_task"]["status"] == "completed"
    assert data["review_task"]["decision"] == "approve"


# ---------------------------------------------------------------------------
# Task003 ERR-1: POST /runs/{run_id}/review returns 404 for unknown run
# ---------------------------------------------------------------------------


def test_review_404_unknown_run(client: TestClient):
    """Task003 ERR-1 test_review_404_unknown_run"""
    resp = client.post("/runs/nonexistent-uuid/review", json={"decision": "approve"})
    assert resp.status_code == 404
    assert "Run not found: nonexistent-uuid" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Task003 ERR-2: POST /runs/{run_id}/review returns 409 for wrong state
# ---------------------------------------------------------------------------


def test_review_409_wrong_state(client: TestClient):
    """Task003 ERR-2 test_review_409_wrong_state"""
    run_id = _create_completed_run(client)

    resp = client.post(f"/runs/{run_id}/review", json={"decision": "approve"})
    assert resp.status_code == 409
    assert "not in review_required status" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Task003 ERR-3: POST /runs/{run_id}/replay returns 404 for unknown run
# ---------------------------------------------------------------------------


def test_replay_404_unknown_run(client: TestClient):
    """Task003 ERR-3 test_replay_404_unknown_run"""
    resp = client.post("/runs/nonexistent-uuid/replay")
    assert resp.status_code == 404
    assert "Run not found: nonexistent-uuid" in resp.json()["detail"]
