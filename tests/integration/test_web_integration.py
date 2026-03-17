"""End-to-end integration tests for web UI flows.
Tests all 4 spec §31 demo paths through the browser UI.
"""

import json

import pytest
from starlette.testclient import TestClient

from app.llm.mock_adapter import MockLLMAdapter
from app.main import create_app

# ---------------------------------------------------------------------------
# Mock LLM responses for different demo paths
# ---------------------------------------------------------------------------

HAPPY_INPUT = "approve this access request"
HAPPY_RESPONSE = json.dumps({
    "request_type": "access_request",
    "employee_name": "Jane Doe",
    "systems_requested": ["salesforce"],
    "manager_name": "Sarah Kim",
    "start_date": "2026-03-15",
    "urgency": "standard",
    "justification": "Need CRM access for onboarding",
})

REVIEW_INPUT = "review this access request"
REVIEW_RESPONSE = json.dumps({
    "request_type": "access_request",
    "employee_name": "John Smith",
    "systems_requested": ["salesforce", "jira"],
    "manager_name": "Sarah Kim",
    "urgency": "high",
    "justification": "Urgent project deadline",
})

REJECT_INPUT = "forbidden system request"
REJECT_RESPONSE = json.dumps({
    "request_type": "access_request",
    "employee_name": "Jane Doe",
    "systems_requested": ["admin_console"],
    "manager_name": "Sarah Kim",
})


@pytest.fixture
def client():
    adapter = MockLLMAdapter(responses={
        HAPPY_INPUT: HAPPY_RESPONSE,
        REVIEW_INPUT: REVIEW_RESPONSE,
        REJECT_INPUT: REJECT_RESPONSE,
        "": HAPPY_RESPONSE,  # empty input still works
    })
    app = create_app("sqlite:///:memory:", llm_adapter=adapter)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Happy path (auto-approve) through UI
# ---------------------------------------------------------------------------


def test_happy_path_through_ui(client: TestClient):
    # 1. Submit intake
    resp = client.post(
        "/ui/intake",
        data={"input_text": HAPPY_INPUT, "mode": "live"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    run_url = resp.headers["location"]
    assert run_url.startswith("/ui/runs/")

    # 2. Verify run detail — auto-approved → completed with effect events
    detail = client.get(run_url)
    assert detail.status_code == 200
    html = detail.text
    assert "completed" in html
    assert "effect.requested" in html
    assert "effect.simulated" in html
    assert "run.completed" in html


# ---------------------------------------------------------------------------
# Review path through UI
# ---------------------------------------------------------------------------


def test_review_path_through_ui(client: TestClient):
    # 1. Submit intake with review-triggering input
    resp = client.post(
        "/ui/intake",
        data={"input_text": REVIEW_INPUT, "mode": "live"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    run_url = resp.headers["location"]
    run_id = run_url.split("/ui/runs/")[1]

    # 2. Verify detail shows review_required with review buttons
    detail = client.get(run_url)
    assert detail.status_code == 200
    html = detail.text
    assert "review_required" in html
    assert "approve" in html.lower()
    assert "reject" in html.lower()

    # 3. Approve the review
    review_resp = client.post(
        f"/ui/runs/{run_id}/review",
        data={"decision": "approve"},
        follow_redirects=False,
    )
    assert review_resp.status_code == 303

    # 4. Verify post-review detail shows completed
    post_detail = client.get(run_url)
    html = post_detail.text
    assert "completed" in html
    assert "review.approved" in html


# ---------------------------------------------------------------------------
# Rejection path through UI
# ---------------------------------------------------------------------------


def test_rejection_path_through_ui(client: TestClient):
    # 1. Submit intake with forbidden system
    resp = client.post(
        "/ui/intake",
        data={"input_text": REJECT_INPUT, "mode": "live"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    run_url = resp.headers["location"]

    # 2. Verify detail — rejected run (forbidden system triggers validation failure)
    detail = client.get(run_url)
    assert detail.status_code == 200
    html = detail.text
    # Forbidden system causes validation failure → proposal_invalid
    assert "proposal_invalid" in html or "completed" in html
    # Should NOT have effect events
    assert "effect.requested" not in html


# ---------------------------------------------------------------------------
# Replay path through UI
# ---------------------------------------------------------------------------


def test_replay_path_through_ui(client: TestClient):
    # 1. Create a completed run
    resp = client.post(
        "/ui/intake",
        data={"input_text": HAPPY_INPUT, "mode": "live"},
        follow_redirects=False,
    )
    run_url = resp.headers["location"]
    run_id = run_url.split("/ui/runs/")[1]

    # 2. Trigger replay from detail context
    replay_resp = client.post(f"/ui/runs/{run_id}/replay")
    assert replay_resp.status_code == 200
    html = replay_resp.text
    assert "replay" in html.lower()
    assert run_id in html
    # Match should be true for a freshly completed run
    assert "Yes" in html


# ---------------------------------------------------------------------------
# DRY_RUN through full UI
# ---------------------------------------------------------------------------


def test_dry_run_through_ui(client: TestClient):
    # 1. Submit intake in dry_run mode
    resp = client.post(
        "/ui/intake",
        data={"input_text": HAPPY_INPUT, "mode": "dry_run"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    run_url = resp.headers["location"]

    # 2. Verify detail — completed but no effect events
    detail = client.get(run_url)
    assert detail.status_code == 200
    html = detail.text
    assert "completed" in html
    assert "dry_run" in html
    # In dry_run, no effect events should appear
    assert "effect.requested" not in html
    assert "effect.simulated" not in html


# ---------------------------------------------------------------------------
# Error recovery during flow
# ---------------------------------------------------------------------------


def test_error_recovery_ui(client: TestClient):
    # Create a review-required run
    resp = client.post(
        "/ui/intake",
        data={"input_text": REVIEW_INPUT, "mode": "live"},
        follow_redirects=False,
    )
    run_url = resp.headers["location"]
    run_id = run_url.split("/ui/runs/")[1]

    # Try to replay a run that's in review_required (not completed) — should error
    replay_resp = client.post(f"/ui/runs/{run_id}/replay")
    assert replay_resp.status_code == 200
    html = replay_resp.text
    # Error page or error message displayed
    assert "error" in html.lower() or "not found" in html.lower()

    # User can navigate back to intake
    intake_resp = client.get("/ui/intake")
    assert intake_resp.status_code == 200
