"""Tests for web UI infrastructure + intake screen.
"""

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.core.runners.base import RunnerError
from app.db.repositories.base import (
    AbstractArtifactRepository,
    AbstractLLMTraceRepository,
    AbstractReceiptRepository,
    AbstractReviewRepository,
)
from app.main import create_app


@pytest.fixture
def client():
    app = create_app("sqlite:///:memory:")
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# input_text in run.received payload
# ---------------------------------------------------------------------------


def test_run_received_contains_input_text(client: TestClient):
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
# Repos on app.state
# ---------------------------------------------------------------------------


def test_app_state_exposes_receipt_and_review_repos(client: TestClient):
    app = client.app
    assert hasattr(app.state, "receipt_repo")
    assert hasattr(app.state, "review_repo")
    assert hasattr(app.state, "artifact_repo")
    assert hasattr(app.state, "llm_trace_repo")
    assert isinstance(app.state.receipt_repo, AbstractReceiptRepository)
    assert isinstance(app.state.review_repo, AbstractReviewRepository)
    assert isinstance(app.state.artifact_repo, AbstractArtifactRepository)
    assert isinstance(app.state.llm_trace_repo, AbstractLLMTraceRepository)


# ---------------------------------------------------------------------------
# Base template renders
# ---------------------------------------------------------------------------


def test_base_template_renders(client: TestClient):
    resp = client.get("/ui/intake")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Base layout structure
    html = resp.text
    assert "<nav" in html or "nav" in html.lower()
    assert "AI Workflow Engine" in html


# ---------------------------------------------------------------------------
# Intake form renders
# ---------------------------------------------------------------------------


def test_intake_form_renders(client: TestClient):
    resp = client.get("/ui/intake")
    assert resp.status_code == 200
    html = resp.text
    assert "<textarea" in html
    assert "<select" in html or 'name="mode"' in html
    assert "live" in html.lower()
    assert "dry_run" in html.lower()
    assert '<button' in html or 'type="submit"' in html


# ---------------------------------------------------------------------------
# Intake submission redirects to run detail
# ---------------------------------------------------------------------------


def test_intake_submission_redirects_to_run_detail(client: TestClient):
    resp = client.post(
        "/ui/intake",
        data={"input_text": "test input", "mode": "live"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/ui/runs/")


# ---------------------------------------------------------------------------
# DRY_RUN mode via intake
# ---------------------------------------------------------------------------


def test_intake_dry_run_mode(client: TestClient):
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
# Empty input text submission
# ---------------------------------------------------------------------------


def test_intake_empty_input(client: TestClient):
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
# Runner error during start_run
# ---------------------------------------------------------------------------


def test_intake_runner_error(client: TestClient):
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
# Unexpected server error
# ---------------------------------------------------------------------------


def test_intake_server_error(client: TestClient):
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
