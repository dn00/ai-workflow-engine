"""Route-level tests for GET /runs/{run_id}/bundle."""

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.core.bundle.models import BundleError


# ---------------------------------------------------------------------------
# test_get_bundle_returns_200
# ---------------------------------------------------------------------------


class TestGetBundleReturns200:
    def test_get_bundle_returns_200(self):
        from datetime import datetime, timezone

        from app.core.bundle.models import ReplayBundle
        from app.core.enums import RunMode, RunStatus
        from app.core.models import Event, Run, VersionInfo
        from app.core.enums import ActorType, EventType
        from app.core.receipts.models import Receipt
        from app.main import create_app

        run = Run(
            run_id="run-test",
            status=RunStatus.COMPLETED,
            mode=RunMode.LIVE,
        )
        event = Event(
            run_id="run-test",
            seq=1,
            event_type=EventType.RUN_RECEIVED,
            version_info=VersionInfo(),
            payload={},
            actor_type=ActorType.SYSTEM,
        )
        receipt = Receipt(
            run_id="run-test",
            raw_response="raw",
            prompt_version="1.0",
        )
        bundle = ReplayBundle(
            exported_at=datetime.now(timezone.utc),
            run=run,
            events=[event],
            receipt=receipt,
            projection={"status": "completed"},
        )

        with patch(
            "app.api.routes.runs.assemble_bundle", return_value=bundle
        ):
            app = create_app(db_url="sqlite:///:memory:")
            with TestClient(app) as client:
                resp = client.get("/runs/run-test/bundle")

        assert resp.status_code == 200
        data = resp.json()
        assert data["bundle_version"] == "1.0"
        assert "exported_at" in data
        assert data["run"]["run_id"] == "run-test"
        assert len(data["events"]) == 1
        assert data["receipt"] is not None
        assert data["projection"] == {"status": "completed"}


# ---------------------------------------------------------------------------
# test_get_bundle_unknown_run_404
# ---------------------------------------------------------------------------


class TestGetBundleUnknownRun404:
    def test_get_bundle_unknown_run_404(self):
        with patch(
            "app.api.routes.runs.assemble_bundle",
            side_effect=BundleError("Run not found: no-such-run"),
        ):
            from app.main import create_app

            app = create_app(db_url="sqlite:///:memory:")
            with TestClient(app) as client:
                resp = client.get("/runs/no-such-run/bundle")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# test_get_bundle_assembly_error_400
# ---------------------------------------------------------------------------


class TestGetBundleAssemblyError400:
    def test_get_bundle_assembly_error_400(self):
        with patch(
            "app.api.routes.runs.assemble_bundle",
            side_effect=BundleError("No events found for run: run-1"),
        ):
            from app.main import create_app

            app = create_app(db_url="sqlite:///:memory:")
            with TestClient(app) as client:
                resp = client.get("/runs/run-1/bundle")

        assert resp.status_code == 400
        assert "No events found" in resp.json()["detail"]
