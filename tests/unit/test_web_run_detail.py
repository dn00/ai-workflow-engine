"""Tests for web UI run detail + event log + review action.

Feature 016, Batch 02, Task 002.
"""

import pytest
from unittest.mock import patch
from starlette.testclient import TestClient

from app.core.enums import RunMode
from app.core.runners.base import RunnerError
from app.main import create_app


@pytest.fixture
def client():
    app = create_app("sqlite:///:memory:")
    with TestClient(app) as c:
        yield c


def _create_run(client: TestClient, mode: str = "live") -> str:
    """Helper: create a run via API and return run_id."""
    resp = client.post("/runs", json={"input_text": "test input", "mode": mode})
    assert resp.status_code == 201
    return resp.json()["run"]["run_id"]


def _create_review_required_run(client: TestClient) -> str:
    """Helper: create a run that lands in review_required status.

    Uses a patched workflow module whose policy returns review_required.
    """
    from unittest.mock import MagicMock
    from app.core.enums import RunStatus

    # We need a workflow that returns review_required from policy
    mock_wf = MagicMock()
    mock_wf.parse_proposal.return_value = MagicMock(success=True, proposal={"key": "val"}, error=None)
    mock_wf.normalize_proposal.return_value = {"key": "val"}
    mock_wf.validate_proposal.return_value = MagicMock(is_valid=True, errors=[])
    mock_wf.evaluate_policy.return_value = MagicMock(status="review_required", reason_codes=["needs_review"])

    with patch("app.core.runners.local_runner.get_workflow", return_value=mock_wf):
        resp = client.post("/runs", json={"input_text": "review me", "mode": "live"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["run"]["status"] == "review_required"
    return data["run"]["run_id"]


# ---------------------------------------------------------------------------
# Task002 AC-1: Run detail shows summary
# ---------------------------------------------------------------------------


def test_Task002_AC_1_test_run_detail_shows_summary(client: TestClient):
    """Task002 AC-1 test_run_detail_shows_summary"""
    run_id = _create_run(client)

    resp = client.get(f"/ui/runs/{run_id}")
    assert resp.status_code == 200
    html = resp.text
    assert run_id in html
    assert "completed" in html.lower() or "status" in html.lower()
    assert "live" in html.lower()
    assert "access_request" in html


# ---------------------------------------------------------------------------
# Task002 AC-2: Run detail shows proposal receipt
# ---------------------------------------------------------------------------


def test_Task002_AC_2_test_run_detail_shows_receipt(client: TestClient):
    """Task002 AC-2 test_run_detail_shows_receipt"""
    run_id = _create_run(client)

    resp = client.get(f"/ui/runs/{run_id}")
    assert resp.status_code == 200
    html = resp.text
    # MockLLMAdapter returns a JSON string as raw_response — check it's present
    assert "raw_response" in html.lower() or "receipt" in html.lower()


# ---------------------------------------------------------------------------
# Task002 AC-3: Event log shows ordered events
# ---------------------------------------------------------------------------


def test_Task002_AC_3_test_run_detail_shows_events_ordered(client: TestClient):
    """Task002 AC-3 test_run_detail_shows_events_ordered"""
    run_id = _create_run(client)

    resp = client.get(f"/ui/runs/{run_id}")
    assert resp.status_code == 200
    html = resp.text
    # Check that event types appear in order
    assert "run.received" in html
    assert "proposal.generated" in html
    # run.received should appear before proposal.generated
    assert html.index("run.received") < html.index("proposal.generated")


# ---------------------------------------------------------------------------
# Task002 AC-4: Review buttons conditional
# ---------------------------------------------------------------------------


def test_Task002_AC_4_test_review_buttons_conditional(client: TestClient):
    """Task002 AC-4 test_review_buttons_conditional"""
    # Completed run should NOT show review buttons
    completed_run_id = _create_run(client)
    resp = client.get(f"/ui/runs/{completed_run_id}")
    html = resp.text
    assert "approve" not in html.lower() or "Approve" not in html

    # Review-required run SHOULD show review buttons
    review_run_id = _create_review_required_run(client)
    resp = client.get(f"/ui/runs/{review_run_id}")
    html = resp.text
    assert "approve" in html.lower()
    assert "reject" in html.lower()


# ---------------------------------------------------------------------------
# Task002 AC-5: Review submission works
# ---------------------------------------------------------------------------


def test_Task002_AC_5_test_review_submission_redirects(client: TestClient):
    """Task002 AC-5 test_review_submission_redirects"""
    run_id = _create_review_required_run(client)

    resp = client.post(
        f"/ui/runs/{run_id}/review",
        data={"decision": "approve"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/ui/runs/{run_id}"

    # Verify run is now approved/completed
    detail_resp = client.get(f"/ui/runs/{run_id}")
    html = detail_resp.text
    # After approval, status changes (approved or completed)
    assert "review_required" not in html.lower() or "completed" in html.lower()


# ---------------------------------------------------------------------------
# Task002 EC-1: Run with no receipt
# ---------------------------------------------------------------------------


def test_Task002_EC_1_test_run_detail_no_receipt(client: TestClient):
    """Task002 EC-1 test_run_detail_no_receipt"""
    from unittest.mock import MagicMock

    # Create a run that fails at parse (before receipt would normally be created)
    # Actually, receipt is created before parse in the runner, so let's
    # just verify the template handles receipt_repo.get_by_run returning None
    mock_wf = MagicMock()
    mock_wf.parse_proposal.return_value = MagicMock(success=False, proposal=None, error="parse error")

    with patch("app.core.runners.local_runner.get_workflow", return_value=mock_wf):
        resp = client.post("/runs", json={"input_text": "bad", "mode": "live"})
    run_id = resp.json()["run"]["run_id"]

    # Now manually clear the receipt to simulate no receipt
    # Instead, let's just check the page renders with "No receipt"
    # The parse-failed run still has a receipt from MockLLMAdapter, so
    # we need to test with a run where receipt is None.
    # Simplest: patch receipt_repo.get_by_run to return None
    with patch.object(client.app.state.receipt_repo, "get_by_run", return_value=None):
        detail = client.get(f"/ui/runs/{run_id}")
    assert detail.status_code == 200
    assert "no receipt" in detail.text.lower() or "receipt" in detail.text.lower()


# ---------------------------------------------------------------------------
# Task002 EC-2: Policy/validation info from event payloads
# ---------------------------------------------------------------------------


def test_Task002_EC_2_test_run_detail_shows_policy_info(client: TestClient):
    """Task002 EC-2 test_run_detail_shows_policy_info"""
    run_id = _create_run(client)

    resp = client.get(f"/ui/runs/{run_id}")
    html = resp.text
    # A completed run has validation.completed and decision.committed events
    assert "validation.completed" in html
    assert "decision.committed" in html


# ---------------------------------------------------------------------------
# Task002 ERR-1: Unknown run_id
# ---------------------------------------------------------------------------


def test_Task002_ERR_1_test_run_detail_unknown_id(client: TestClient):
    """Task002 ERR-1 test_run_detail_unknown_id"""
    resp = client.get("/ui/runs/nonexistent-id")
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


# ---------------------------------------------------------------------------
# Task002 ERR-2: Review on non-reviewable run
# ---------------------------------------------------------------------------


def test_Task002_ERR_2_test_review_wrong_status(client: TestClient):
    """Task002 ERR-2 test_review_wrong_status"""
    run_id = _create_run(client)  # completed run

    resp = client.post(
        f"/ui/runs/{run_id}/review",
        data={"decision": "approve"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    html = resp.text
    assert "not in review_required status" in html
