"""Tests for API schemas, dependencies, and app wiring."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.enums import RunMode, RunStatus
from app.core.models import Run


# ---------------------------------------------------------------------------
# App starts with lifespan and serves requests
# ---------------------------------------------------------------------------


def test_app_starts_with_lifespan():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app("sqlite:///:memory:")

    # Verify app was created
    assert app is not None
    assert app.title == "AI Workflow Engine"

    # Verify runner is available after lifespan starts (use TestClient)
    from starlette.testclient import TestClient

    with TestClient(app) as client:
        # app.state.runner should be set by lifespan
        assert hasattr(app.state, "runner")
        assert app.state.runner is not None
        assert hasattr(app.state, "run_repo")
        assert app.state.run_repo is not None
        assert hasattr(app.state, "event_repo")
        assert app.state.event_repo is not None


# ---------------------------------------------------------------------------
# CreateRunRequest validates correct input
# ---------------------------------------------------------------------------


def test_create_run_request_valid():
    from app.api.schemas.runs import CreateRunRequest

    req = CreateRunRequest(input_text="test request", mode="live")
    assert req.input_text == "test request"
    assert req.mode == "live"

    # Also test with dry_run mode
    req2 = CreateRunRequest(input_text="another request", mode="dry_run")
    assert req2.mode == "dry_run"


# ---------------------------------------------------------------------------
# SubmitReviewRequest validates correct input
# ---------------------------------------------------------------------------


def test_submit_review_request_valid():
    from app.api.schemas.runs import SubmitReviewRequest

    req = SubmitReviewRequest(decision="approve")
    assert req.decision == "approve"

    req2 = SubmitReviewRequest(decision="reject")
    assert req2.decision == "reject"


# ---------------------------------------------------------------------------
# Response schemas serialize domain models
# ---------------------------------------------------------------------------


def test_response_schema_serializes_domain_model():
    from app.api.schemas.runs import RunResponse

    now = datetime.now(timezone.utc)
    run = Run(
        run_id="run-123",
        workflow_type="access_request",
        status=RunStatus.RECEIVED,
        mode=RunMode.LIVE,
        created_at=now,
        updated_at=now,
        current_projection=None,
    )

    # Serialize domain model through RunResponse
    response = RunResponse.model_validate(run.model_dump())
    assert response.run_id == "run-123"
    assert response.workflow_type == "access_request"
    assert response.status == "received"
    assert response.mode == "live"
    assert response.created_at == now
    assert response.updated_at == now
    assert response.current_projection is None


# ---------------------------------------------------------------------------
# CreateRunRequest defaults mode to "live"
# ---------------------------------------------------------------------------


def test_create_run_request_default_mode():
    from app.api.schemas.runs import CreateRunRequest

    req = CreateRunRequest(input_text="test")
    assert req.mode == "live"


# ---------------------------------------------------------------------------
# CreateRunRequest rejects missing input_text
# ---------------------------------------------------------------------------


def test_create_run_request_missing_input_text():
    from app.api.schemas.runs import CreateRunRequest

    with pytest.raises(ValidationError) as exc_info:
        CreateRunRequest()  # type: ignore[call-arg]

    # Should mention field required
    errors = exc_info.value.errors()
    assert any(e["type"] == "missing" for e in errors)
