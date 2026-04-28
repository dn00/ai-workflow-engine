"""Tests for ReplayBundle model + assemble_bundle."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.core.artifacts.models import Artifact
from app.core.enums import ActorType, EventType, RunMode, RunStatus
from app.core.models import Event, Run, VersionInfo
from app.core.receipts.models import Receipt
from app.observability.llm_traces import LLMTrace

# ---------------------------------------------------------------------------
# Helpers — mock repos
# ---------------------------------------------------------------------------

def _make_run(run_id: str = "run-1", projection: dict | None = None) -> Run:
    return Run(
        run_id=run_id,
        workflow_type="access_request",
        status=RunStatus.COMPLETED,
        mode=RunMode.LIVE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        current_projection=projection,
    )


def _make_event(run_id: str, seq: int) -> Event:
    return Event(
        run_id=run_id,
        seq=seq,
        event_type=EventType.RUN_RECEIVED,
        version_info=VersionInfo(),
        payload={"seq": seq},
        actor_type=ActorType.SYSTEM,
    )


def _make_receipt(run_id: str) -> Receipt:
    return Receipt(
        run_id=run_id,
        raw_response="raw-llm-response",
        prompt_version="1.0",
        model_id="test-model",
    )


def _make_artifact(run_id: str) -> Artifact:
    return Artifact(
        run_id=run_id,
        artifact_type="access_request.proposal",
        data={"request_type": "access_request"},
        source_receipt_id="receipt-1",
    )


def _make_llm_trace(run_id: str) -> LLMTrace:
    return LLMTrace(
        run_id=run_id,
        workflow_type="access_request",
        prompt_version="1.0",
        latency_ms=5,
        input_chars=10,
        response_chars=100,
        parse_success=True,
        policy_status="approved",
    )


def _mock_repos(
    run: Run | None,
    events: list[Event] | None = None,
    receipt: Receipt | None = None,
    artifacts: list[Artifact] | None = None,
    llm_traces: list[LLMTrace] | None = None,
):
    run_repo = MagicMock()
    run_repo.get.return_value = run

    event_repo = MagicMock()
    event_repo.list_by_run.return_value = events if events is not None else []

    receipt_repo = MagicMock()
    receipt_repo.get_by_run.return_value = receipt

    artifact_repo = MagicMock()
    artifact_repo.list_by_run.return_value = artifacts if artifacts is not None else []

    llm_trace_repo = MagicMock()
    llm_trace_repo.list_by_run.return_value = (
        llm_traces if llm_traces is not None else []
    )

    return run_repo, event_repo, receipt_repo, artifact_repo, llm_trace_repo


# ---------------------------------------------------------------------------
# test_assemble_bundle_complete_run
# ---------------------------------------------------------------------------


class TestAssembleBundleCompleteRun:
    def test_assemble_bundle_complete_run(self):
        from app.core.bundle import assemble_bundle

        run = _make_run(projection={"status": "completed"})
        events = [_make_event("run-1", seq=1), _make_event("run-1", seq=2)]
        receipt = _make_receipt("run-1")
        artifacts = [_make_artifact("run-1")]
        llm_traces = [_make_llm_trace("run-1")]
        run_repo, event_repo, receipt_repo, artifact_repo, llm_trace_repo = _mock_repos(
            run, events, receipt, artifacts, llm_traces
        )

        bundle = assemble_bundle(
            "run-1",
            run_repo,
            event_repo,
            receipt_repo,
            artifact_repo,
            llm_trace_repo,
        )

        assert bundle.run == run
        assert bundle.events == events
        assert bundle.receipt == receipt
        assert bundle.artifacts == artifacts
        assert bundle.llm_traces == llm_traces
        assert bundle.projection == run.current_projection


# ---------------------------------------------------------------------------
# test_bundle_metadata_fields
# ---------------------------------------------------------------------------


class TestBundleMetadataFields:
    def test_bundle_metadata_fields(self):
        from app.core.bundle import assemble_bundle

        run = _make_run()
        events = [_make_event("run-1", seq=1)]
        run_repo, event_repo, receipt_repo, _artifact_repo, _llm_trace_repo = _mock_repos(
            run, events, None
        )

        before = datetime.now(timezone.utc)
        bundle = assemble_bundle("run-1", run_repo, event_repo, receipt_repo)
        after = datetime.now(timezone.utc)

        assert bundle.bundle_version == "1.0"
        assert before <= bundle.exported_at <= after


# ---------------------------------------------------------------------------
# test_bundle_events_ordered_by_seq
# ---------------------------------------------------------------------------


class TestBundleEventsOrderedBySeq:
    def test_bundle_events_ordered_by_seq(self):
        from app.core.bundle import assemble_bundle

        run = _make_run()
        # list_by_run returns events in seq order per spec
        events = [_make_event("run-1", seq=i) for i in range(1, 4)]
        run_repo, event_repo, receipt_repo, _artifact_repo, _llm_trace_repo = _mock_repos(
            run, events, None
        )

        bundle = assemble_bundle("run-1", run_repo, event_repo, receipt_repo)

        seqs = [e.seq for e in bundle.events]
        assert seqs == [1, 2, 3]


# ---------------------------------------------------------------------------
# test_bundle_barrel_exports
# ---------------------------------------------------------------------------


class TestBundleBarrelExports:
    def test_bundle_barrel_exports(self):
        # Bundle-level imports
        from app.core.bundle import BundleError, ReplayBundle, assemble_bundle

        assert ReplayBundle is not None
        assert BundleError is not None
        assert callable(assemble_bundle)

        # Core-level imports
        from app.core import BundleError as CoreBundleError
        from app.core import ReplayBundle as CoreReplayBundle
        from app.core import assemble_bundle as core_assemble_bundle

        assert CoreReplayBundle is ReplayBundle
        assert CoreBundleError is BundleError
        assert core_assemble_bundle is assemble_bundle


# ---------------------------------------------------------------------------
# test_bundle_no_receipt
# ---------------------------------------------------------------------------


class TestBundleNoReceipt:
    def test_bundle_no_receipt(self):
        from app.core.bundle import assemble_bundle

        run = _make_run()
        events = [_make_event("run-1", seq=1)]
        run_repo, event_repo, receipt_repo, _artifact_repo, _llm_trace_repo = _mock_repos(
            run, events, None
        )

        bundle = assemble_bundle("run-1", run_repo, event_repo, receipt_repo)

        assert bundle.receipt is None


# ---------------------------------------------------------------------------
# test_bundle_no_projection
# ---------------------------------------------------------------------------


class TestBundleNoProjection:
    def test_bundle_no_projection(self):
        from app.core.bundle import assemble_bundle

        run = _make_run(projection=None)
        events = [_make_event("run-1", seq=1)]
        run_repo, event_repo, receipt_repo, _artifact_repo, _llm_trace_repo = _mock_repos(
            run, events, None
        )

        bundle = assemble_bundle("run-1", run_repo, event_repo, receipt_repo)

        assert bundle.projection is None


# ---------------------------------------------------------------------------
# test_bundle_unknown_run
# ---------------------------------------------------------------------------


class TestBundleUnknownRun:
    def test_bundle_unknown_run(self):
        from app.core.bundle import BundleError, assemble_bundle

        run_repo, event_repo, receipt_repo, _artifact_repo, _llm_trace_repo = _mock_repos(run=None)

        with pytest.raises(BundleError, match="Run not found"):
            assemble_bundle("nonexistent", run_repo, event_repo, receipt_repo)


# ---------------------------------------------------------------------------
# test_bundle_no_events
# ---------------------------------------------------------------------------


class TestBundleNoEvents:
    def test_bundle_no_events(self):
        from app.core.bundle import BundleError, assemble_bundle

        run = _make_run()
        run_repo, event_repo, receipt_repo, _artifact_repo, _llm_trace_repo = _mock_repos(
            run, events=[], receipt=None
        )

        with pytest.raises(BundleError, match="No events found"):
            assemble_bundle("run-1", run_repo, event_repo, receipt_repo)
