"""Tests for web UI infrastructure + intake screen.

Feature 016, Batch 01, Task 001.
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.core.enums import RunMode, EventType
from app.core.runners.base import RunnerError
from app.db.repositories.base import AbstractReceiptRepository, AbstractReviewRepository
from app.main import create_app


@pytest.fixture
def client():
    app = create_app("sqlite:///:memory:")
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Task001 AC-1: input_text in run.received payload
# ---------------------------------------------------------------------------


def test_Task001_AC_1_test_run_received_contains_input_text(client: TestClient):
    """Task001 AC-1 test_run_received_contains_input_text"""
    # Create a run via the API
    resp = client.post("/runs", json={"input_text": "Hello IT", "mode": "live"})
    assert resp.status_code == 201
    run_id = resp.json()["run"]["run_id"]

    # Fetch events
    events_resp = client.get(f"/runs/{run_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()["events"]

    # Find the run.received event
    received = [e for e in events if e["event_type"] == "run.received"]
    assert len(received) == 1
    assert received[0]["payload"] == {"input_text": "Hello IT"}


# ---------------------------------------------------------------------------
# Task001 AC-2: Repos on app.state
# ---------------------------------------------------------------------------


def test_Task001_AC_2_test_app_state_exposes_receipt_and_review_repos(client: TestClient):
    """Task001 AC-2 test_app_state_exposes_receipt_and_review_repos"""
    app = client.app
    assert hasattr(app.state, "receipt_repo")
    assert hasattr(app.state, "review_repo")
    assert isinstance(app.state.receipt_repo, AbstractReceiptRepository)
    assert isinstance(app.state.review_repo, AbstractReviewRepository)


# ---------------------------------------------------------------------------
# Task001 AC-3: Base template renders
# ---------------------------------------------------------------------------


def test_Task001_AC_3_test_base_template_renders(client: TestClient):
    """Task001 AC-3 test_base_template_renders"""
    resp = client.get("/ui/intake")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Base layout structure
    html = resp.text
    assert "<nav" in html or "nav" in html.lower()
    assert "AI Workflow Engine" in html


# ---------------------------------------------------------------------------
# Task001 AC-4: Intake form renders
# ---------------------------------------------------------------------------


def test_Task001_AC_4_test_intake_form_renders(client: TestClient):
    """Task001 AC-4 test_intake_form_renders"""
    resp = client.get("/ui/intake")
    assert resp.status_code == 200
    html = resp.text
    assert "<textarea" in html
    assert "<select" in html or 'name="mode"' in html
    assert "live" in html.lower()
    assert "dry_run" in html.lower()
    assert '<button' in html or 'type="submit"' in html


# ---------------------------------------------------------------------------
# Task001 AC-5: Intake submission redirects to run detail
# ---------------------------------------------------------------------------


def test_Task001_AC_5_test_intake_submission_redirects_to_run_detail(client: TestClient):
    """Task001 AC-5 test_intake_submission_redirects_to_run_detail"""
    resp = client.post(
        "/ui/intake",
        data={"input_text": "test input", "mode": "live"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/ui/runs/")


# ---------------------------------------------------------------------------
# Task001 EC-1: DRY_RUN mode via intake
# ---------------------------------------------------------------------------


def test_Task001_EC_1_test_intake_dry_run_mode(client: TestClient):
    """Task001 EC-1 test_intake_dry_run_mode"""
    resp = client.post(
        "/ui/intake",
        data={"input_text": "test input", "mode": "dry_run"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/ui/runs/")

    # Verify the run was created in dry_run mode
    run_id = location.split("/ui/runs/")[1]
    run_resp = client.get(f"/runs/{run_id}")
    assert run_resp.status_code == 200
    assert run_resp.json()["mode"] == "dry_run"


# ---------------------------------------------------------------------------
# Task001 EC-2: Empty input text submission
# ---------------------------------------------------------------------------


def test_Task001_EC_2_test_intake_empty_input(client: TestClient):
    """Task001 EC-2 test_intake_empty_input"""
    resp = client.post(
        "/ui/intake",
        data={"input_text": "", "mode": "live"},
        follow_redirects=False,
    )
    # Should not crash — runner processes empty text
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/ui/runs/")


# ---------------------------------------------------------------------------
# Task001 ERR-1: Runner error during start_run
# ---------------------------------------------------------------------------


def test_Task001_ERR_1_test_intake_runner_error(client: TestClient):
    """Task001 ERR-1 test_intake_runner_error"""
    with patch.object(
        client.app.state.runner, "start_run", side_effect=RunnerError("Workflow not registered")
    ):
        resp = client.post(
            "/ui/intake",
            data={"input_text": "test", "mode": "live"},
            follow_redirects=False,
        )
    assert resp.status_code == 200
    html = resp.text
    assert "Workflow not registered" in html


# ---------------------------------------------------------------------------
# Task001 ERR-2: Unexpected server error
# ---------------------------------------------------------------------------


def test_Task001_ERR_2_test_intake_server_error(client: TestClient):
    """Task001 ERR-2 test_intake_server_error"""
    with patch.object(
        client.app.state.runner, "start_run", side_effect=RuntimeError("kaboom")
    ):
        resp = client.post(
            "/ui/intake",
            data={"input_text": "test", "mode": "live"},
            follow_redirects=False,
        )
    assert resp.status_code == 500
    html = resp.text
    assert "error" in html.lower()
