"""Integration tests for LocalRunner demo paths.

Uses real SQLite (in-memory), real repositories, real workflow module,
and the actual LocalRunner. Verifies event counts, seq ordering, and
projection storage.
"""

import json

import pytest

import app.workflows  # noqa: F401 — triggers register_workflow

from app.core.enums import EventType, ReviewDecision, RunMode, RunStatus
from app.core.runners import LocalRunner, RunnerError
from app.core.replay.models import ReplayResult
from app.db import (
    SQLiteEventRepository,
    SQLiteReviewRepository,
    SQLiteRunRepository,
    enable_sqlite_fk_pragma,
    get_engine,
    get_session_factory,
    init_db,
)
from app.db.repositories.receipt_repository import SQLiteReceiptRepository
from app.effects.simulated import SimulatedEffectAdapter
from app.llm.mock_adapter import MockLLMAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

HAPPY_PATH_JSON = json.dumps({
    "request_type": "access_request",
    "employee_name": "Jane Doe",
    "systems_requested": ["salesforce"],
    "manager_name": "Sarah Kim",
    "start_date": "2026-03-15",
    "urgency": "standard",
    "justification": "Need CRM access for onboarding",
})

REVIEW_REQUIRED_JSON = json.dumps({
    "request_type": "access_request",
    "employee_name": "John Smith",
    "systems_requested": ["salesforce", "jira"],
    "manager_name": "Sarah Kim",
    "urgency": "high",
    "justification": "Urgent project deadline",
})

FORBIDDEN_SYSTEM_JSON = json.dumps({
    "request_type": "access_request",
    "employee_name": "Jane Doe",
    "systems_requested": ["admin_console"],
    "manager_name": "Sarah Kim",
})

PARSE_FAILURE_INPUT = "not valid json"


@pytest.fixture
def runner_env():
    """Set up in-memory SQLite + real repos + LocalRunner."""
    engine = get_engine("sqlite:///:memory:")
    enable_sqlite_fk_pragma(engine)
    init_db(engine)
    sf = get_session_factory(engine)

    run_repo = SQLiteRunRepository(sf)
    event_repo = SQLiteEventRepository(sf)
    review_repo = SQLiteReviewRepository(sf)
    effect_adapter = SimulatedEffectAdapter()
    llm_adapter = MockLLMAdapter(responses={
        HAPPY_PATH_JSON: HAPPY_PATH_JSON,
        REVIEW_REQUIRED_JSON: REVIEW_REQUIRED_JSON,
        FORBIDDEN_SYSTEM_JSON: FORBIDDEN_SYSTEM_JSON,
        PARSE_FAILURE_INPUT: PARSE_FAILURE_INPUT,
    })
    receipt_repo = SQLiteReceiptRepository(sf)

    runner = LocalRunner(run_repo, event_repo, review_repo, effect_adapter, llm_adapter, receipt_repo)

    return runner, run_repo, event_repo, review_repo, receipt_repo


# ---------------------------------------------------------------------------
# Demo 1 — Happy path end-to-end
# ---------------------------------------------------------------------------


def test_demo_1_happy_path(runner_env):
    runner, run_repo, event_repo, review_repo, _receipt_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)

    assert result.projection.status == RunStatus.COMPLETED
    events = event_repo.list_by_run(result.run.run_id)
    assert len(events) == 7

    # Verify effect.simulated is present
    event_types = [e.event_type for e in events]
    assert EventType.EFFECT_SIMULATED in event_types


# ---------------------------------------------------------------------------
# Demo 2 — Review path end-to-end
# ---------------------------------------------------------------------------


def test_demo_2_review_path(runner_env):
    runner, run_repo, event_repo, review_repo, _receipt_repo = runner_env

    # Phase 1: start_run → review_required
    result1 = runner.start_run(REVIEW_REQUIRED_JSON, RunMode.LIVE)
    assert result1.projection.status == RunStatus.REVIEW_REQUIRED
    assert result1.review_task is not None

    # Phase 2: submit_review → completed
    result2 = runner.submit_review(result1.run.run_id, ReviewDecision.APPROVE)
    assert result2.projection.status == RunStatus.COMPLETED

    events = event_repo.list_by_run(result1.run.run_id)
    assert len(events) == 9


# ---------------------------------------------------------------------------
# Demo 3 — Validation failure (forbidden system) end-to-end
# ---------------------------------------------------------------------------


def test_demo_3_validation_failure_forbidden(runner_env):
    runner, run_repo, event_repo, review_repo, _receipt_repo = runner_env

    result = runner.start_run(FORBIDDEN_SYSTEM_JSON, RunMode.LIVE)

    assert result.projection.status == RunStatus.PROPOSAL_INVALID
    events = event_repo.list_by_run(result.run.run_id)
    assert len(events) == 3

    event_types = [e.event_type for e in events]
    assert event_types == [
        EventType.RUN_RECEIVED,
        EventType.PROPOSAL_GENERATED,
        EventType.VALIDATION_FAILED,
    ]


# ---------------------------------------------------------------------------
# Demo 4 — Replay end-to-end
# ---------------------------------------------------------------------------


def test_demo_4_replay(runner_env):
    runner, run_repo, event_repo, review_repo, _receipt_repo = runner_env

    # First complete a run
    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)
    run_id = result.run.run_id

    # Replay it
    replay_result = runner.replay_run(run_id)

    assert isinstance(replay_result, ReplayResult)
    assert replay_result.match is True
    assert replay_result.event_count == 7


# ---------------------------------------------------------------------------
# DRY_RUN end-to-end
# ---------------------------------------------------------------------------


def test_dry_run_end_to_end(runner_env):
    runner, run_repo, event_repo, review_repo, _receipt_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.DRY_RUN)

    assert result.projection.status == RunStatus.COMPLETED
    events = event_repo.list_by_run(result.run.run_id)
    assert len(events) == 5

    event_types = [e.event_type for e in events]
    assert EventType.EFFECT_REQUESTED not in event_types
    assert EventType.EFFECT_SIMULATED not in event_types


# ---------------------------------------------------------------------------
# Event count matches expected per path [parametrized]
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "input_json, mode, expected_count, desc",
    [
        (HAPPY_PATH_JSON, RunMode.LIVE, 7, "happy_live"),
        (FORBIDDEN_SYSTEM_JSON, RunMode.LIVE, 3, "validation_failure"),
        (HAPPY_PATH_JSON, RunMode.DRY_RUN, 5, "dry_run"),
    ],
    ids=["happy_live", "validation_failure", "dry_run"],
)
def test_event_counts_per_path(runner_env, input_json, mode, expected_count, desc):
    runner, run_repo, event_repo, review_repo, _receipt_repo = runner_env

    result = runner.start_run(input_json, mode)
    events = event_repo.list_by_run(result.run.run_id)
    assert len(events) == expected_count, f"Path {desc}: expected {expected_count}, got {len(events)}"


# ---------------------------------------------------------------------------
# Projection stored correctly after completion
# ---------------------------------------------------------------------------


def test_projection_stored_correctly(runner_env):
    runner, run_repo, event_repo, review_repo, _receipt_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)

    # Reload run from DB
    stored_run = run_repo.get(result.run.run_id)
    assert stored_run.current_projection is not None

    # Compare stored projection with result projection
    result_proj_dict = result.projection.model_dump(mode="json")
    assert stored_run.current_projection == result_proj_dict


# ---------------------------------------------------------------------------
# Seq numbers contiguous within a run
# ---------------------------------------------------------------------------


def test_seq_numbers_contiguous(runner_env):
    runner, run_repo, event_repo, review_repo, _receipt_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)
    events = event_repo.list_by_run(result.run.run_id)

    seqs = [e.seq for e in events]
    assert seqs == list(range(1, len(events) + 1))


# ---------------------------------------------------------------------------
# submit_review on completed run raises
# ---------------------------------------------------------------------------


def test_submit_review_on_completed_run_raises(runner_env):
    runner, run_repo, event_repo, review_repo, _receipt_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)
    assert result.projection.status == RunStatus.COMPLETED

    with pytest.raises(RunnerError, match="not in review_required status"):
        runner.submit_review(result.run.run_id, ReviewDecision.APPROVE)


# ===========================================================================
# End-to-end integration tests (Task 003)
# ===========================================================================


# ---------------------------------------------------------------------------
# End-to-end happy path with receipt stored
# ---------------------------------------------------------------------------


def test_e2e_happy_path_receipt_stored(runner_env):
    runner, run_repo, event_repo, review_repo, receipt_repo = runner_env

    result = runner.start_run("New hire needs Salesforce", RunMode.LIVE)

    assert result.projection.status == RunStatus.COMPLETED

    # Receipt exists in DB
    receipt = receipt_repo.get_by_run(result.run.run_id)
    assert receipt is not None
    # raw_response matches MockLLMAdapter default output
    from app.llm.mock_adapter import DEFAULT_RESPONSE

    assert receipt.raw_response == DEFAULT_RESPONSE


# ---------------------------------------------------------------------------
# End-to-end prompt_version on events
# ---------------------------------------------------------------------------


def test_e2e_prompt_version_on_events(runner_env):
    runner, run_repo, event_repo, review_repo, receipt_repo = runner_env

    result = runner.start_run("New hire needs Salesforce", RunMode.LIVE)

    events = event_repo.list_by_run(result.run.run_id)
    # All events after run.received carry prompt_version from LLM
    post_received = [e for e in events if e.event_type != EventType.RUN_RECEIVED]
    for e in post_received:
        assert e.version_info.prompt_version == "1.0"


# ---------------------------------------------------------------------------
# End-to-end review path with receipt stored
# ---------------------------------------------------------------------------


def test_e2e_review_path_receipt_stored(runner_env):
    runner, run_repo, event_repo, review_repo, receipt_repo = runner_env

    result1 = runner.start_run(REVIEW_REQUIRED_JSON, RunMode.LIVE)
    assert result1.projection.status == RunStatus.REVIEW_REQUIRED

    # Receipt stored before review boundary
    receipt = receipt_repo.get_by_run(result1.run.run_id)
    assert receipt is not None

    # Complete the review
    result2 = runner.submit_review(result1.run.run_id, ReviewDecision.APPROVE)
    assert result2.projection.status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# Parse failure still stores receipt
# ---------------------------------------------------------------------------


def test_e2e_parse_failure_receipt_stored(runner_env):
    runner, run_repo, event_repo, review_repo, receipt_repo = runner_env

    result = runner.start_run(PARSE_FAILURE_INPUT, RunMode.LIVE)
    assert result.projection.status == RunStatus.PROPOSAL_INVALID

    # Receipt still stored even though parse failed
    receipt = receipt_repo.get_by_run(result.run.run_id)
    assert receipt is not None
    assert receipt.raw_response == PARSE_FAILURE_INPUT


# ---------------------------------------------------------------------------
# Receipt raw_response matches LLM output exactly
# ---------------------------------------------------------------------------


def test_e2e_receipt_matches_llm_output(runner_env):
    runner, run_repo, event_repo, review_repo, receipt_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)

    receipt = receipt_repo.get_by_run(result.run.run_id)
    assert receipt is not None
    # MockLLMAdapter with pass-through responses: raw_response == HAPPY_PATH_JSON
    assert receipt.raw_response == HAPPY_PATH_JSON


# ---------------------------------------------------------------------------
# LLM error prevents receipt storage
# ---------------------------------------------------------------------------


def test_e2e_llm_error_no_receipt():
    from unittest.mock import MagicMock

    from app.llm.base import LLMAdapterError

    # Build a fresh env with a failing LLM adapter
    engine = get_engine("sqlite:///:memory:")
    enable_sqlite_fk_pragma(engine)
    init_db(engine)
    sf = get_session_factory(engine)

    run_repo = SQLiteRunRepository(sf)
    event_repo = SQLiteEventRepository(sf)
    review_repo = SQLiteReviewRepository(sf)
    effect_adapter = SimulatedEffectAdapter()
    receipt_repo = SQLiteReceiptRepository(sf)

    failing_adapter = MagicMock()
    failing_adapter.generate_proposal.side_effect = LLMAdapterError("Service down")

    runner = LocalRunner(run_repo, event_repo, review_repo, effect_adapter, failing_adapter, receipt_repo)

    with pytest.raises(RunnerError, match="LLM|proposal generation"):
        runner.start_run("any input", RunMode.LIVE)

    # Run was created but LLM error happens before receipt storage
    # Check that the receipts table has zero rows
    from sqlalchemy import text

    with sf() as session:
        count = session.execute(text("SELECT COUNT(*) FROM receipts")).scalar()
    assert count == 0
