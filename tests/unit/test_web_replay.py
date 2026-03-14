"""Tests for web UI replay result view.

Feature 016, Batch 02, Task 003.
"""

import pytest
from unittest.mock import patch
from starlette.testclient import TestClient

from app.core.runners.base import RunnerError
from app.main import create_app


@pytest.fixture
def client():
    app = create_app("sqlite:///:memory:")
    with TestClient(app) as c:
        yield c


def _create_run(client: TestClient) -> str:
    """Helper: create a completed run and return run_id."""
    resp = client.post("/runs", json={"input_text": "test input", "mode": "live"})
    assert resp.status_code == 201
    return resp.json()["run"]["run_id"]


# ---------------------------------------------------------------------------
# Task003 AC-1: Replay triggers and renders
# ---------------------------------------------------------------------------


def test_Task003_AC_1_test_replay_renders_result(client: TestClient):
    """Task003 AC-1 test_replay_renders_result"""
    run_id = _create_run(client)

    resp = client.post(f"/ui/runs/{run_id}/replay", follow_redirects=False)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    html = resp.text
    assert "replay" in html.lower()
    assert run_id in html


# ---------------------------------------------------------------------------
# Task003 AC-2: Match status displayed
# ---------------------------------------------------------------------------


def test_Task003_AC_2_test_replay_shows_match_status(client: TestClient):
    """Task003 AC-2 test_replay_shows_match_status"""
    run_id = _create_run(client)

    resp = client.post(f"/ui/runs/{run_id}/replay")
    html = resp.text
    # Should show match indicator — either "Yes" or "No"
    assert "match" in html.lower()


# ---------------------------------------------------------------------------
# Task003 AC-3: Projections displayed
# ---------------------------------------------------------------------------


def test_Task003_AC_3_test_replay_shows_projections(client: TestClient):
    """Task003 AC-3 test_replay_shows_projections"""
    run_id = _create_run(client)

    resp = client.post(f"/ui/runs/{run_id}/replay")
    html = resp.text
    assert "replayed" in html.lower() or "projection" in html.lower()
    assert "stored" in html.lower() or "projection" in html.lower()


# ---------------------------------------------------------------------------
# Task003 EC-1: Replay with no stored projection
# ---------------------------------------------------------------------------


def test_Task003_EC_1_test_replay_no_stored_projection(client: TestClient):
    """Task003 EC-1 test_replay_no_stored_projection"""
    from app.core.replay.models import ReplayResult

    run_id = _create_run(client)

    # Patch runner.replay_run to return a result with no stored projection
    mock_result = ReplayResult(
        run_id=run_id,
        replayed_projection=None,
        stored_projection=None,
        match=False,
        event_count=5,
        error=None,
    )
    with patch.object(client.app.state.runner, "replay_run", return_value=mock_result):
        resp = client.post(f"/ui/runs/{run_id}/replay")

    assert resp.status_code == 200
    html = resp.text
    assert "no stored projection" in html.lower() or "none" in html.lower()


# ---------------------------------------------------------------------------
# Task003 ERR-1: Replay of unknown run_id
# ---------------------------------------------------------------------------


def test_Task003_ERR_1_test_replay_unknown_run(client: TestClient):
    """Task003 ERR-1 test_replay_unknown_run"""
    resp = client.post("/ui/runs/nonexistent-id/replay", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.text
    assert "not found" in html.lower() or "error" in html.lower()
