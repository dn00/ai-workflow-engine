"""Tests for run endpoints: POST /runs, GET /runs/{run_id}, GET /runs/{run_id}/events.

Feature 014, Batch 02, Task 002.
"""

import pytest
from starlette.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app("sqlite:///:memory:")
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Task002 AC-1: POST /runs creates and returns a completed run
# ---------------------------------------------------------------------------


def test_post_runs_happy_path(client: TestClient):
    """Task002 AC-1 test_post_runs_happy_path"""
    resp = client.post("/runs", json={"input_text": "test input", "mode": "live"})
    assert resp.status_code == 201
    data = resp.json()
    assert "run" in data
    assert "projection" in data
    assert data["run"]["run_id"]
    assert data["run"]["status"] == "completed"
    assert data["projection"] is not None
    assert data["review_task"] is None


# ---------------------------------------------------------------------------
# Task002 AC-2: GET /runs/{run_id} returns run summary
# ---------------------------------------------------------------------------


def test_get_run_summary(client: TestClient):
    """Task002 AC-2 test_get_run_summary"""
    # Create a run first
    create_resp = client.post("/runs", json={"input_text": "test input", "mode": "live"})
    run_id = create_resp.json()["run"]["run_id"]

    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["workflow_type"] == "access_request"
    assert data["status"] == "completed"
    assert data["mode"] == "live"
    assert "created_at" in data
    assert "updated_at" in data
    assert data["current_projection"] is not None


# ---------------------------------------------------------------------------
# Task002 AC-3: GET /runs/{run_id}/events returns event list
# ---------------------------------------------------------------------------


def test_get_run_events(client: TestClient):
    """Task002 AC-3 test_get_run_events"""
    create_resp = client.post("/runs", json={"input_text": "test input", "mode": "live"})
    run_id = create_resp.json()["run"]["run_id"]

    resp = client.get(f"/runs/{run_id}/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert len(data["events"]) > 0

    # Verify events are ordered by seq
    seqs = [e["seq"] for e in data["events"]]
    assert seqs == sorted(seqs)

    # Each event has required fields
    first = data["events"][0]
    assert "event_id" in first
    assert "event_type" in first
    assert "timestamp" in first
    assert "payload" in first
    assert "actor_type" in first
    assert "version_info" in first


# ---------------------------------------------------------------------------
# Task002 AC-4: POST /runs with mode=dry_run skips effects
# ---------------------------------------------------------------------------


def test_post_runs_dry_run(client: TestClient):
    """Task002 AC-4 test_post_runs_dry_run"""
    resp = client.post("/runs", json={"input_text": "test input", "mode": "dry_run"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["run"]["status"] == "completed"

    # Verify no effect.simulated event
    run_id = data["run"]["run_id"]
    events_resp = client.get(f"/runs/{run_id}/events")
    event_types = [e["event_type"] for e in events_resp.json()["events"]]
    assert "effect.simulated" not in event_types


# ---------------------------------------------------------------------------
# Task002 EC-1: POST /runs with no mode field defaults to live
# ---------------------------------------------------------------------------


def test_post_runs_default_mode(client: TestClient):
    """Task002 EC-1 test_post_runs_default_mode"""
    resp = client.post("/runs", json={"input_text": "test input"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["run"]["mode"] == "live"


# ---------------------------------------------------------------------------
# Task002 EC-2: GET /runs/{run_id}/events returns events for minimal run
# ---------------------------------------------------------------------------


def test_get_events_minimal(client: TestClient):
    """Task002 EC-2 test_get_events_minimal"""
    create_resp = client.post("/runs", json={"input_text": "test input"})
    run_id = create_resp.json()["run"]["run_id"]

    resp = client.get(f"/runs/{run_id}/events")
    assert resp.status_code == 200
    events = resp.json()["events"]
    # Synchronous runner always produces at least initial events
    assert len(events) >= 1


# ---------------------------------------------------------------------------
# Task002 ERR-1: GET /runs/{run_id} returns 404 for unknown run_id
# ---------------------------------------------------------------------------


def test_get_run_404(client: TestClient):
    """Task002 ERR-1 test_get_run_404"""
    resp = client.get("/runs/nonexistent-uuid")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Run not found: nonexistent-uuid"


# ---------------------------------------------------------------------------
# Task002 ERR-2: GET /runs/{run_id}/events returns 404 for unknown run_id
# ---------------------------------------------------------------------------


def test_get_events_404(client: TestClient):
    """Task002 ERR-2 test_get_events_404"""
    resp = client.get("/runs/nonexistent-uuid/events")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Run not found: nonexistent-uuid"


# ---------------------------------------------------------------------------
# Task002 ERR-3: POST /runs returns 400 for mode=replay
# ---------------------------------------------------------------------------


def test_post_runs_replay_mode_400(client: TestClient):
    """Task002 ERR-3 test_post_runs_replay_mode_400"""
    resp = client.post("/runs", json={"input_text": "test", "mode": "replay"})
    assert resp.status_code == 400
    assert "replay" in resp.json()["detail"].lower()
