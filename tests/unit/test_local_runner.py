"""Tests for LocalRunner start_run + helpers."""

from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from app.core.enums import (
    EventType,
    ReviewDecision,
    RunMode,
    RunStatus,
)
from app.core.models import Event, Run, ValidatedDecision
from app.core.replay.models import ReplayResult
from app.core.runners.base import RunnerError
from app.core.runners.local_runner import LocalRunner
from app.core.runners.models import RunResult
from app.llm.base import LLMAdapterError
from app.llm.mock_adapter import MockLLMAdapter

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
            return_value=_FakeParseResult(
                success=True, proposal={"request_type": "access_request"}
            )
        )
    else:
        mod.parse_proposal = MagicMock(
            return_value=_FakeParseResult(success=False, error="bad json")
        )

    mod.normalize_proposal = MagicMock(return_value=MagicMock())

    mod.validate_proposal = MagicMock(
        return_value=_FakeValidationResult(
            is_valid=validation_valid,
            errors=[] if validation_valid else ["validation error"],
        )
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
    receipt_repo = MagicMock()

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
    run_repo.update_status.side_effect = lambda rid, status, ts: Run(
        run_id=rid, status=status
    )
    # run_repo.update_projection returns a run
    run_repo.update_projection.side_effect = lambda rid, proj, ts: Run(
        run_id=rid, current_projection=proj
    )

    # review_repo.create returns whatever is passed in
    review_repo.create.side_effect = lambda r: r

    # receipt_repo.create returns whatever is passed in
    receipt_repo.create.side_effect = lambda r: r

    return run_repo, event_repo, review_repo, receipt_repo, _events


def _make_effect_adapter():
    """Create a mock effect adapter."""
    adapter = MagicMock()
    adapter.execute.return_value = {"status": "simulated", "task_id": "sim-1"}
    return adapter


# ---------------------------------------------------------------------------
# start_run happy path (approved, LIVE)
# ---------------------------------------------------------------------------


def test_start_run_happy_path_approved_live():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# start_run parse failure
# ---------------------------------------------------------------------------


def test_start_run_parse_failure():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=False)

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# start_run validation failure
# ---------------------------------------------------------------------------


def test_start_run_validation_failure():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=False)

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# start_run rejected
# ---------------------------------------------------------------------------


def test_start_run_rejected():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="rejected")

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# start_run review_required
# ---------------------------------------------------------------------------


def test_start_run_review_required():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(
        parse_success=True,
        validation_valid=True,
        policy_status="review_required",
    )

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# start_run DRY_RUN approved
# ---------------------------------------------------------------------------


def test_start_run_dry_run_approved():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# Seq numbers monotonically increasing
# ---------------------------------------------------------------------------


def test_start_run_seq_numbers_contiguous():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run('{"any": "json"}', RunMode.LIVE)

    seqs = [e.seq for e in events]
    assert seqs == list(range(1, len(events) + 1))


# ---------------------------------------------------------------------------
# version_info on all events
# ---------------------------------------------------------------------------


def test_start_run_version_info_on_all_events():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run('{"any": "json"}', RunMode.LIVE)

    for e in events:
        assert e.version_info is not None
        assert e.version_info.policy_version == "1.0"


# ---------------------------------------------------------------------------
# Idempotency key on effect.requested
# ---------------------------------------------------------------------------


def test_start_run_idempotency_key_on_effect_requested():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run('{"any": "json"}', RunMode.LIVE)

    effect_requested = [e for e in events if e.event_type == EventType.EFFECT_REQUESTED]
    assert len(effect_requested) == 1
    assert effect_requested[0].idempotency_key is not None
    # Should be a UUID string
    assert len(effect_requested[0].idempotency_key) > 0


# ---------------------------------------------------------------------------
# REPLAY mode raises RunnerError
# ---------------------------------------------------------------------------


def test_start_run_replay_mode_raises():
    run_repo, event_repo, review_repo, receipt_repo, _ = _make_repos()
    adapter = _make_effect_adapter()

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    with pytest.raises(RunnerError, match="replay_run|REPLAY"):
        runner.start_run('{"any": "json"}', RunMode.REPLAY)


# ---------------------------------------------------------------------------
# Unknown workflow_type raises RunnerError
# ---------------------------------------------------------------------------


def test_start_run_unknown_workflow_type_raises():
    run_repo, event_repo, review_repo, receipt_repo, _ = _make_repos()
    adapter = _make_effect_adapter()

    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    # Patch get_workflow to raise ValueError (unknown type)
    with patch(
        "app.core.runners.local_runner.get_workflow",
        side_effect=ValueError("Unknown workflow type: 'bogus'"),
    ):
        with pytest.raises(RunnerError, match="Unknown workflow type"):
            runner.start_run('{"any": "json"}', RunMode.LIVE)


# ===========================================================================
# Runner integration (Task 002)
# ===========================================================================


# ---------------------------------------------------------------------------
# start_run calls LLM and stores receipt
# ---------------------------------------------------------------------------


def test_start_run_calls_llm_and_stores_receipt():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run("some input", RunMode.LIVE)

    # receipt_repo.create must have been called with a Receipt containing the LLM raw_response
    receipt_repo.create.assert_called_once()
    receipt_arg = receipt_repo.create.call_args[0][0]
    from app.core.receipts.models import Receipt

    assert isinstance(receipt_arg, Receipt)
    llm_response = llm_adapter.generate_proposal("some input", "access_request")
    assert receipt_arg.raw_response == llm_response.raw_response


# ---------------------------------------------------------------------------
# start_run wires prompt_version from LLM response
# ---------------------------------------------------------------------------


def test_start_run_wires_prompt_version():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run("some input", RunMode.LIVE)

    # All events after run.received should carry the LLM's prompt_version
    post_received = [e for e in events if e.event_type != EventType.RUN_RECEIVED]
    for e in post_received:
        assert e.version_info.prompt_version == "1.0"  # MockLLMAdapter default


# ---------------------------------------------------------------------------
# start_run passes LLM response to parser, not input_text
# ---------------------------------------------------------------------------


def test_start_run_passes_llm_response_to_parser():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run("plain text input", RunMode.LIVE)

    # parse_proposal should receive LLM output, not "plain text input"
    call_args = wf.parse_proposal.call_args[0][0]
    assert call_args != "plain text input"
    # It should be the LLM's raw_response (the MockLLMAdapter default JSON)
    llm_output = llm_adapter.generate_proposal("plain text input", "access_request").raw_response
    assert call_args == llm_output


# ---------------------------------------------------------------------------
# DRY_RUN mode calls LLM and stores receipt
# ---------------------------------------------------------------------------


def test_start_run_dry_run_calls_llm():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)
    wf = _make_workflow_module(parse_success=True, validation_valid=True, policy_status="approved")

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run("input", RunMode.DRY_RUN)

    # LLM was called and receipt was stored
    receipt_repo.create.assert_called_once()
    # Effects not applied (DRY_RUN)
    adapter.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Parse failure stores receipt before failing
# ---------------------------------------------------------------------------


def test_start_run_parse_failure_stores_receipt():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)
    wf = _make_workflow_module(parse_success=False)

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        result = runner.start_run("input", RunMode.LIVE)

    # Even though parse failed, receipt should still be stored
    receipt_repo.create.assert_called_once()
    assert result.projection.status == RunStatus.PROPOSAL_INVALID


# ---------------------------------------------------------------------------
# Successful parse stores inspectable artifacts when repository is configured
# ---------------------------------------------------------------------------


def test_start_run_stores_proposal_and_normalized_artifacts():
    run_repo, event_repo, review_repo, receipt_repo, _events = _make_repos()
    artifact_repo = MagicMock()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(
        run_repo,
        event_repo,
        review_repo,
        adapter,
        llm_adapter,
        receipt_repo,
        artifact_repo=artifact_repo,
    )
    wf = _make_workflow_module(
        parse_success=True, validation_valid=True, policy_status="approved"
    )

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        runner.start_run("input", RunMode.LIVE)

    assert artifact_repo.create.call_count == 2
    artifact_types = [
        call.args[0].artifact_type for call in artifact_repo.create.call_args_list
    ]
    assert artifact_types == [
        "access_request.proposal",
        "access_request.normalized",
    ]
    assert artifact_repo.create.call_args_list[0].args[0].source_receipt_id


# ---------------------------------------------------------------------------
# LLM adapter error raised as RunnerError
# ---------------------------------------------------------------------------


def test_start_run_llm_error_raises_runner_error():
    run_repo, event_repo, review_repo, receipt_repo, _ = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MagicMock()
    llm_adapter.generate_proposal.side_effect = LLMAdapterError("LLM service unavailable")
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)
    wf = _make_workflow_module()

    with patch("app.core.runners.local_runner.get_workflow", return_value=wf):
        with pytest.raises(RunnerError, match="LLM|proposal generation"):
            runner.start_run("input", RunMode.LIVE)


# ===========================================================================
# submit_review + replay_run tests
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
# submit_review approve resumes and completes (LIVE)
# ---------------------------------------------------------------------------


def test_submit_review_approve_live():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# submit_review reject completes without effect
# ---------------------------------------------------------------------------


def test_submit_review_reject():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# submit_review updates ReviewTask
# ---------------------------------------------------------------------------


def test_submit_review_updates_review_task():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# replay_run returns ReplayResult
# ---------------------------------------------------------------------------


def test_replay_run_delegates_to_engine():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    # Set up a run with projection
    run_repo.get.side_effect = lambda rid: Run(
        run_id=rid, current_projection={"run_id": rid, "status": "completed"}
    )

    mock_replay_result = ReplayResult(run_id="r-1", match=True, event_count=7)

    with patch(
        "app.core.runners.local_runner._replay_run_engine",
        return_value=mock_replay_result,
    ) as mock_engine:
        result = runner.replay_run("r-1")

    assert isinstance(result, ReplayResult)
    assert result.match is True
    mock_engine.assert_called_once()


# ---------------------------------------------------------------------------
# submit_review approve in DRY_RUN mode
# ---------------------------------------------------------------------------


def test_submit_review_approve_dry_run():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

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
# replay_run with no events
# ---------------------------------------------------------------------------


def test_replay_run_no_events():
    run_repo, event_repo, review_repo, receipt_repo, events = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    run_repo.get.side_effect = lambda rid: Run(run_id=rid, current_projection=None)
    # event_repo.list_by_run returns empty (no events for this run)

    result = runner.replay_run("r-empty")

    assert isinstance(result, ReplayResult)
    # Replay engine handles empty events → error
    assert result.error is not None


# ---------------------------------------------------------------------------
# submit_review on non-review_required status
# ---------------------------------------------------------------------------


def test_submit_review_wrong_status_raises():
    run_repo, event_repo, review_repo, receipt_repo, _ = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    run_repo.get.side_effect = lambda rid: Run(
        run_id=rid, status=RunStatus.COMPLETED
    )

    with pytest.raises(RunnerError, match="not in review_required status"):
        runner.submit_review("r-done", ReviewDecision.APPROVE)


# ---------------------------------------------------------------------------
# submit_review on unknown run_id
# ---------------------------------------------------------------------------


def test_submit_review_unknown_run_raises():
    run_repo, event_repo, review_repo, receipt_repo, _ = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    run_repo.get.side_effect = None
    run_repo.get.return_value = None

    with pytest.raises(RunnerError, match="Run not found"):
        runner.submit_review("nonexistent", ReviewDecision.APPROVE)


# ---------------------------------------------------------------------------
# replay_run on unknown run_id
# ---------------------------------------------------------------------------


def test_replay_run_unknown_run_raises():
    run_repo, event_repo, review_repo, receipt_repo, _ = _make_repos()
    adapter = _make_effect_adapter()
    llm_adapter = MockLLMAdapter()
    runner = LocalRunner(run_repo, event_repo, review_repo, adapter, llm_adapter, receipt_repo)

    run_repo.get.side_effect = None
    run_repo.get.return_value = None

    with pytest.raises(RunnerError, match="Run not found"):
        runner.replay_run("nonexistent")
