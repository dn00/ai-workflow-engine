"""Tests for LocalRunner start_run + helpers (Feature 009, Batch 02, Task 002)."""

from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from app.core.enums import (
    ActorType,
    EventType,
    ReviewDecision,
    RunMode,
    RunStatus,
)
from app.core.models import Event, ReviewTask, Run, ValidatedDecision, VersionInfo
from app.core.projections.models import RunProjection
from app.core.runners.base import RunnerError
from app.core.runners.local_runner import LocalRunner
from app.core.runners.models import RunResult


# ---------------------------------------------------------------------------
# Helpers — mock workflow module + repos
# ---------------------------------------------------------------------------


class _FakeParseResult(BaseModel):
    success: bool
    proposal: dict | None = None
    error: str | None = None


class _FakeValidationResult(BaseModel):
    is_valid: bool
    errors: list[str] = []


def _make_workflow_module(
    parse_success: bool = True,
    validation_valid: bool = True,
    policy_status: str = "approved",
) -> ModuleType:
    """Build a mock workflow module with controlled outcomes."""
    mod = ModuleType("fake_workflow")

    if parse_success:
        mod.parse_proposal = MagicMock(
            return_value=_FakeParseResult(success=True, proposal={"request_type": "access_request"})
        )
    else:
        mod.parse_proposal = MagicMock(
            return_value=_FakeParseResult(success=False, error="bad json")
        )

    mod.normalize_proposal = MagicMock(return_value=MagicMock())

    mod.validate_proposal = MagicMock(
        return_value=_FakeValidationResult(is_valid=validation_valid, errors=[] if validation_valid else ["validation error"])
    )

    mod.evaluate_policy = MagicMock(
        return_value=ValidatedDecision(
            status=policy_status,
            reason_codes=[] if policy_status == "approved" else ["reason"],
            normalized_fields={},
            allowed_actions=[],
        )
    )

    return mod


def _make_repos():
    """Create mock repos that track appended events and created objects."""
    run_repo = MagicMock()
    event_repo = MagicMock()
    review_repo = MagicMock()

    # event_repo.append returns whatever is passed in
    event_repo.append.side_effect = lambda e: e
    # event_repo.list_by_run returns all appended events
    _events: list[Event] = []

    def _append(e):
        _events.append(e)
        return e

    def _list_by_run(run_id):
        return [e for e in _events if e.run_id == run_id]

    event_repo.append.side_effect = _append
    event_repo.list_by_run.side_effect = _list_by_run

    # run_repo.create returns whatever is passed in
    run_repo.create.side_effect = lambda r: r
    # run_repo.get returns a run
    run_repo.get.side_effect = lambda run_id: Run(run_id=run_id)
    # run_repo.update_status returns a run
    run_repo.update_status.side_effect = lambda rid, status, ts: Run(run_id=rid, status=status)
    # run_repo.update_projection returns a run
    run_repo.update_projection.side_effect = lambda rid, proj, ts: Run(run_id=rid, current_projection=proj)

    # review_repo.create returns whatever is passed in
    review_repo.create.side_effect = lambda r: r

    return run_repo, event_repo, review_repo, _events


def _make_effect_adapter():
    """Create a mock effect adapter."""
    adapter = MagicMock()
    adapter.execute.return_value = {"status": "simulated", "task_id": "sim-1"}
    return adapter


# ---------------------------------------------------------------------------
# Task002 AC-1: start_run happy path (approved, LIVE)
# ---------------------------------------------------------------------------


def test_Task002_AC_1_test_start_run_happy_path_approved_live():
    """Task002 AC-1 test_start_run_happy_path_approved_live"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        result = runner.start_run('{"request_type": "access_request"}', RunMode.LIVE)

    assert isinstance(result, RunResult)
    assert result.projection.status == RunStatus.COMPLETED
    assert len(events) == 7

    expected_types = [
        EventType.RUN_RECEIVED,
        EventType.PROPOSAL_GENERATED,
        EventType.VALIDATION_COMPLETED,
        EventType.DECISION_COMMITTED,
        EventType.EFFECT_REQUESTED,
        EventType.EFFECT_SIMULATED,
        EventType.RUN_COMPLETED,
    ]
    assert [e.event_type for e in events] == expected_types
    adapter.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Task002 AC-2: start_run parse failure
# ---------------------------------------------------------------------------


def test_Task002_AC_2_test_start_run_parse_failure():
    """Task002 AC-2 test_start_run_parse_failure"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=False)

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        result = runner.start_run("not json", RunMode.LIVE)

    assert result.projection.status == RunStatus.PROPOSAL_INVALID
    assert len(events) == 2

    expected_types = [EventType.RUN_RECEIVED, EventType.PROPOSAL_PARSE_FAILED]
    assert [e.event_type for e in events] == expected_types

    # No further pipeline calls after parse failure
    wf.normalize_proposal.assert_not_called()
    wf.validate_proposal.assert_not_called()
    wf.evaluate_policy.assert_not_called()


# ---------------------------------------------------------------------------
# Task002 AC-3: start_run validation failure
# ---------------------------------------------------------------------------


def test_Task002_AC_3_test_start_run_validation_failure():
    """Task002 AC-3 test_start_run_validation_failure"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=False)

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        result = runner.start_run('{"any": "json"}', RunMode.LIVE)

    assert result.projection.status == RunStatus.PROPOSAL_INVALID
    assert len(events) == 3

    expected_types = [
        EventType.RUN_RECEIVED,
        EventType.PROPOSAL_GENERATED,
        EventType.VALIDATION_FAILED,
    ]
    assert [e.event_type for e in events] == expected_types


# ---------------------------------------------------------------------------
# Task002 AC-4: start_run rejected
# ---------------------------------------------------------------------------


def test_Task002_AC_4_test_start_run_rejected():
    """Task002 AC-4 test_start_run_rejected"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="rejected")

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        result = runner.start_run('{"any": "json"}', RunMode.LIVE)

    assert result.projection.status == RunStatus.COMPLETED
    assert len(events) == 5

    expected_types = [
        EventType.RUN_RECEIVED,
        EventType.PROPOSAL_GENERATED,
        EventType.VALIDATION_COMPLETED,
        EventType.DECISION_COMMITTED,
        EventType.RUN_COMPLETED,
    ]
    assert [e.event_type for e in events] == expected_types
    adapter.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Task002 AC-5: start_run review_required
# ---------------------------------------------------------------------------


def test_Task002_AC_5_test_start_run_review_required():
    """Task002 AC-5 test_start_run_review_required"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="review_required")

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        result = runner.start_run('{"any": "json"}', RunMode.LIVE)

    assert result.projection.status == RunStatus.REVIEW_REQUIRED
    assert len(events) == 5

    expected_types = [
        EventType.RUN_RECEIVED,
        EventType.PROPOSAL_GENERATED,
        EventType.VALIDATION_COMPLETED,
        EventType.DECISION_COMMITTED,
        EventType.REVIEW_REQUESTED,
    ]
    assert [e.event_type for e in events] == expected_types
    assert result.review_task is not None
    review_repo.create.assert_called_once()


# ---------------------------------------------------------------------------
# Task002 AC-6: start_run DRY_RUN approved
# ---------------------------------------------------------------------------


def test_Task002_AC_6_test_start_run_dry_run_approved():
    """Task002 AC-6 test_start_run_dry_run_approved"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        result = runner.start_run('{"any": "json"}', RunMode.DRY_RUN)

    assert result.projection.status == RunStatus.COMPLETED
    # DRY_RUN: no effect.requested / effect.simulated → 5 events
    assert len(events) == 5

    expected_types = [
        EventType.RUN_RECEIVED,
        EventType.PROPOSAL_GENERATED,
        EventType.VALIDATION_COMPLETED,
        EventType.DECISION_COMMITTED,
        EventType.RUN_COMPLETED,
    ]
    assert [e.event_type for e in events] == expected_types
    adapter.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Task002 EC-1: Seq numbers monotonically increasing
# ---------------------------------------------------------------------------


def test_Task002_EC_1_test_start_run_seq_numbers_contiguous():
    """Task002 EC-1 test_start_run_seq_numbers_contiguous"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run('{"any": "json"}', RunMode.LIVE)

    seqs = [e.seq for e in events]
    assert seqs == list(range(1, len(events) + 1))


# ---------------------------------------------------------------------------
# Task002 EC-2: version_info on all events
# ---------------------------------------------------------------------------


def test_Task002_EC_2_test_start_run_version_info_on_all_events():
    """Task002 EC-2 test_start_run_version_info_on_all_events"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run('{"any": "json"}', RunMode.LIVE)

    for e in events:
        assert e.version_info is not None
        assert e.version_info.policy_version == "1.0"


# ---------------------------------------------------------------------------
# Task002 EC-3: Idempotency key on effect.requested
# ---------------------------------------------------------------------------


def test_Task002_EC_3_test_start_run_idempotency_key_on_effect_requested():
    """Task002 EC-3 test_start_run_idempotency_key_on_effect_requested"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run('{"any": "json"}', RunMode.LIVE)

    effect_requested = [e for e in events if e.event_type == EventType.EFFECT_REQUESTED]
    assert len(effect_requested) == 1
    assert effect_requested[0].idempotency_key is not None
    # Should be a UUID string
    assert len(effect_requested[0].idempotency_key) > 0


# ---------------------------------------------------------------------------
# Task002 ERR-1: REPLAY mode raises RunnerError
# ---------------------------------------------------------------------------


def test_Task002_ERR_1_test_start_run_replay_mode_raises():
    """Task002 ERR-1 test_start_run_replay_mode_raises"""
    run_repo, event_repo, review_repo, _ = _make_repos()
    adapter = _make_effect_adapter()

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    with pytest.raises(RunnerError, match="replay_run|REPLAY"):
        runner.start_run('{"any": "json"}', RunMode.REPLAY)


# ---------------------------------------------------------------------------
# Task002 ERR-2: Unknown workflow_type raises RunnerError
# ---------------------------------------------------------------------------


def test_Task002_ERR_2_test_start_run_unknown_workflow_type_raises():
    """Task002 ERR-2 test_start_run_unknown_workflow_type_raises"""
    run_repo, event_repo, review_repo, _ = _make_repos()
    adapter = _make_effect_adapter()

    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    # Patch get_workflow to raise ValueError (unknown type)
    with patch(
        "app.core.runners.local_runner.get_workflow",
        side_effect=ValueError("Unknown workflow type: 'bogus'"),
    ):
        with pytest.raises(RunnerError, match="Unknown workflow type"):
            runner.start_run('{"any": "json"}', RunMode.LIVE)


# ===========================================================================
# Batch 03 — submit_review + replay_run tests (Task 003)
# ===========================================================================


def _start_run_to_review(runner, events_list):
    """Helper: run start_run to review_required state, return (run_id, review_task)."""
    wf = _make_workflow_module(
        parse_success=True, validation_valid=True, policy_status="review_required"
    )
    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        result = runner.start_run('{"any": "json"}', RunMode.LIVE)
    return result.run.run_id, result.review_task


def _start_run_to_review_dry(runner, events_list):
    """Helper: run start_run to review_required in DRY_RUN mode."""
    wf = _make_workflow_module(
        parse_success=True, validation_valid=True, policy_status="review_required"
    )
    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        result = runner.start_run('{"any": "json"}', RunMode.DRY_RUN)
    return result.run.run_id, result.review_task


# ---------------------------------------------------------------------------
# Task003 AC-1: submit_review approve resumes and completes (LIVE)
# ---------------------------------------------------------------------------


def test_Task003_AC_1_test_submit_review_approve_live():
    """Task003 AC-1 test_submit_review_approve_live"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    run_id, review_task = _start_run_to_review(runner, events)

    # Set up run_repo.get to return run with review_required status and LIVE mode
    run_repo.get.side_effect = lambda rid: Run(
        run_id=rid, status=RunStatus.REVIEW_REQUIRED, mode=RunMode.LIVE
    )
    review_repo.get_by_run.return_value = review_task
    review_repo.update_decision.side_effect = lambda rid, dec, ts: review_task

    events_before = len(events)
    result = runner.submit_review(run_id, ReviewDecision.APPROVE)

    assert result.projection.status == RunStatus.COMPLETED
    new_events = events[events_before:]
    new_types = [e.event_type for e in new_events]
    assert EventType.REVIEW_APPROVED in new_types
    assert EventType.EFFECT_REQUESTED in new_types
    assert EventType.EFFECT_SIMULATED in new_types
    assert EventType.RUN_COMPLETED in new_types
    adapter.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Task003 AC-2: submit_review reject completes without effect
# ---------------------------------------------------------------------------


def test_Task003_AC_2_test_submit_review_reject():
    """Task003 AC-2 test_submit_review_reject"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    run_id, review_task = _start_run_to_review(runner, events)

    run_repo.get.side_effect = lambda rid: Run(
        run_id=rid, status=RunStatus.REVIEW_REQUIRED, mode=RunMode.LIVE
    )
    review_repo.get_by_run.return_value = review_task
    review_repo.update_decision.side_effect = lambda rid, dec, ts: review_task

    events_before = len(events)
    result = runner.submit_review(run_id, ReviewDecision.REJECT)

    assert result.projection.status == RunStatus.COMPLETED
    new_events = events[events_before:]
    new_types = [e.event_type for e in new_events]
    assert EventType.REVIEW_REJECTED in new_types
    assert EventType.RUN_COMPLETED in new_types
    assert EventType.EFFECT_REQUESTED not in new_types
    adapter.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Task003 AC-3: submit_review updates ReviewTask
# ---------------------------------------------------------------------------


def test_Task003_AC_3_test_submit_review_updates_review_task():
    """Task003 AC-3 test_submit_review_updates_review_task"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    run_id, review_task = _start_run_to_review(runner, events)

    run_repo.get.side_effect = lambda rid: Run(
        run_id=rid, status=RunStatus.REVIEW_REQUIRED, mode=RunMode.LIVE
    )
    review_repo.get_by_run.return_value = review_task
    review_repo.update_decision.side_effect = lambda rid, dec, ts: review_task

    runner.submit_review(run_id, ReviewDecision.APPROVE)

    review_repo.update_decision.assert_called_once()
    call_args = review_repo.update_decision.call_args
    assert call_args[0][0] == review_task.review_id
    assert call_args[0][1] == ReviewDecision.APPROVE


# ---------------------------------------------------------------------------
# Task003 AC-4: replay_run returns ReplayResult
# ---------------------------------------------------------------------------


def test_Task003_AC_4_test_replay_run_delegates_to_engine():
    """Task003 AC-4 test_replay_run_delegates_to_engine"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    # Set up a run with projection
    run_repo.get.side_effect = lambda rid: Run(
        run_id=rid, current_projection={"run_id": rid, "status": "completed"}
    )

    from app.core.replay.models import ReplayResult as RR

    mock_replay_result = RR(run_id="r-1", match=True, event_count=7)

    with patch(
        "app.core.runners.local_runner._replay_run_engine",
        return_value=mock_replay_result,
    ) as mock_engine:
        result = runner.replay_run("r-1")

    assert isinstance(result, RR)
    assert result.match is True
    mock_engine.assert_called_once()


# ---------------------------------------------------------------------------
# Task003 EC-1: submit_review approve in DRY_RUN mode
# ---------------------------------------------------------------------------


def test_Task003_EC_1_test_submit_review_approve_dry_run():
    """Task003 EC-1 test_submit_review_approve_dry_run"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    run_id, review_task = _start_run_to_review_dry(runner, events)

    run_repo.get.side_effect = lambda rid: Run(
        run_id=rid, status=RunStatus.REVIEW_REQUIRED, mode=RunMode.DRY_RUN
    )
    review_repo.get_by_run.return_value = review_task
    review_repo.update_decision.side_effect = lambda rid, dec, ts: review_task

    events_before = len(events)
    result = runner.submit_review(run_id, ReviewDecision.APPROVE)

    assert result.projection.status == RunStatus.COMPLETED
    new_events = events[events_before:]
    new_types = [e.event_type for e in new_events]
    # DRY_RUN: no effect events
    assert EventType.EFFECT_REQUESTED not in new_types
    assert EventType.EFFECT_SIMULATED not in new_types
    assert EventType.RUN_COMPLETED in new_types
    adapter.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Task003 EC-2: replay_run with no events
# ---------------------------------------------------------------------------


def test_Task003_EC_2_test_replay_run_no_events():
    """Task003 EC-2 test_replay_run_no_events"""
    run_repo, event_repo, review_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    run_repo.get.side_effect = lambda rid: Run(run_id=rid, current_projection=None)
    # event_repo.list_by_run returns empty (no events for this run)

    from app.core.replay.models import ReplayResult as RR

    result = runner.replay_run("r-empty")

    assert isinstance(result, RR)
    # Replay engine handles empty events → error
    assert result.error is not None


# ---------------------------------------------------------------------------
# Task003 ERR-1: submit_review on non-review_required status
# ---------------------------------------------------------------------------


def test_Task003_ERR_1_test_submit_review_wrong_status_raises():
    """Task003 ERR-1 test_submit_review_wrong_status_raises"""
    run_repo, event_repo, review_repo, _ = _make_repos()
    adapter = _make_effect_adapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    run_repo.get.side_effect = lambda rid: Run(
        run_id=rid, status=RunStatus.COMPLETED
    )

    with pytest.raises(RunnerError, match="not in review_required status"):
        runner.submit_review("r-done", ReviewDecision.APPROVE)


# ---------------------------------------------------------------------------
# Task003 ERR-2: submit_review on unknown run_id
# ---------------------------------------------------------------------------


def test_Task003_ERR_2_test_submit_review_unknown_run_raises():
    """Task003 ERR-2 test_submit_review_unknown_run_raises"""
    run_repo, event_repo, review_repo, _ = _make_repos()
    adapter = _make_effect_adapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    run_repo.get.side_effect = None
    run_repo.get.return_value = None

    with pytest.raises(RunnerError, match="Run not found"):
        runner.submit_review("nonexistent", ReviewDecision.APPROVE)


# ---------------------------------------------------------------------------
# Task003 ERR-3: replay_run on unknown run_id
# ---------------------------------------------------------------------------


def test_Task003_ERR_3_test_replay_run_unknown_run_raises():
    """Task003 ERR-3 test_replay_run_unknown_run_raises"""
    run_repo, event_repo, review_repo, _ = _make_repos()
    adapter = _make_effect_adapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter)

    run_repo.get.side_effect = None
    run_repo.get.return_value = None

    with pytest.raises(RunnerError, match="Run not found"):
        runner.replay_run("nonexistent")
