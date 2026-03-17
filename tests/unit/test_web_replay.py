"""Tests for web UI replay result view.
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
# Replay triggers and renders
# ---------------------------------------------------------------------------


def test_replay_renders_result(client: TestClient):
    run_id = _create_run(client)

    resp = client.post(f"/ui/runs/{run_id}/replay", follow_redirects=False)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    html = resp.text
    assert "replay" in html.lower()
    assert run_id in html


# ---------------------------------------------------------------------------
# Match status displayed
# ---------------------------------------------------------------------------


def test_replay_shows_match_status(client: TestClient):
    run_id = _create_run(client)

    resp = client.post(f"/ui/runs/{run_id}/replay")
    html = resp.text
    # Should show match indicator — either "Yes" or "No"
    assert "match" in html.lower()


# ---------------------------------------------------------------------------
# Projections displayed
# ---------------------------------------------------------------------------


def test_replay_shows_projections(client: TestClient):
    run_id = _create_run(client)

    resp = client.post(f"/ui/runs/{run_id}/replay")
    html = resp.text
    assert "replayed" in html.lower() or "projection" in html.lower()
    assert "stored" in html.lower() or "projection" in html.lower()


# ---------------------------------------------------------------------------
# Replay with no stored projection
# ---------------------------------------------------------------------------


def test_replay_no_stored_projection(client: TestClient):
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
# Replay of unknown run_id
# ---------------------------------------------------------------------------


def test_replay_unknown_run(client: TestClient):
    resp = client.post("/ui/runs/nonexistent-id/replay", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.text
    assert "not found" in html.lower() or "error" in html.lower()
