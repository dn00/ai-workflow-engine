"""Integration tests for LocalRunner demo paths (Feature 009, Batch 04, Task 004).

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
from app.effects.simulated import SimulatedEffectAdapter


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

    runner = LocalRunner(run_repo, event_repo, review_repo, effect_adapter)

    return runner, run_repo, event_repo, review_repo


# ---------------------------------------------------------------------------
# Task004 AC-1: Demo 1 — Happy path end-to-end
# ---------------------------------------------------------------------------


def test_Task004_AC_1_test_demo_1_happy_path(runner_env):
    """Task004 AC-1 test_demo_1_happy_path"""
    runner, run_repo, event_repo, review_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)

    assert result.projection.status == RunStatus.COMPLETED
    events = event_repo.list_by_run(result.run.run_id)
    assert len(events) == 7

    # Verify effect.simulated is present
    event_types = [e.event_type for e in events]
    assert EventType.EFFECT_SIMULATED in event_types


# ---------------------------------------------------------------------------
# Task004 AC-2: Demo 2 — Review path end-to-end
# ---------------------------------------------------------------------------


def test_Task004_AC_2_test_demo_2_review_path(runner_env):
    """Task004 AC-2 test_demo_2_review_path"""
    runner, run_repo, event_repo, review_repo = runner_env

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
# Task004 AC-3: Demo 3 — Validation failure (forbidden system) end-to-end
# ---------------------------------------------------------------------------


def test_Task004_AC_3_test_demo_3_validation_failure_forbidden(runner_env):
    """Task004 AC-3 test_demo_3_validation_failure_forbidden"""
    runner, run_repo, event_repo, review_repo = runner_env

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
# Task004 AC-4: Demo 4 — Replay end-to-end
# ---------------------------------------------------------------------------


def test_Task004_AC_4_test_demo_4_replay(runner_env):
    """Task004 AC-4 test_demo_4_replay"""
    runner, run_repo, event_repo, review_repo = runner_env

    # First complete a run
    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)
    run_id = result.run.run_id

    # Replay it
    replay_result = runner.replay_run(run_id)

    assert isinstance(replay_result, ReplayResult)
    assert replay_result.match is True
    assert replay_result.event_count == 7


# ---------------------------------------------------------------------------
# Task004 AC-5: DRY_RUN end-to-end
# ---------------------------------------------------------------------------


def test_Task004_AC_5_test_dry_run_end_to_end(runner_env):
    """Task004 AC-5 test_dry_run_end_to_end"""
    runner, run_repo, event_repo, review_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.DRY_RUN)

    assert result.projection.status == RunStatus.COMPLETED
    events = event_repo.list_by_run(result.run.run_id)
    assert len(events) == 5

    event_types = [e.event_type for e in events]
    assert EventType.EFFECT_REQUESTED not in event_types
    assert EventType.EFFECT_SIMULATED not in event_types


# ---------------------------------------------------------------------------
# Task004 EC-1: Event count matches expected per path [parametrized]
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
def test_Task004_EC_1_test_event_counts_per_path(runner_env, input_json, mode, expected_count, desc):
    """Task004 EC-1 test_event_counts_per_path [parametrized]"""
    runner, run_repo, event_repo, review_repo = runner_env

    result = runner.start_run(input_json, mode)
    events = event_repo.list_by_run(result.run.run_id)
    assert len(events) == expected_count, f"Path {desc}: expected {expected_count}, got {len(events)}"


# ---------------------------------------------------------------------------
# Task004 EC-2: Projection stored correctly after completion
# ---------------------------------------------------------------------------


def test_Task004_EC_2_test_projection_stored_correctly(runner_env):
    """Task004 EC-2 test_projection_stored_correctly"""
    runner, run_repo, event_repo, review_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)

    # Reload run from DB
    stored_run = run_repo.get(result.run.run_id)
    assert stored_run.current_projection is not None

    # Compare stored projection with result projection
    result_proj_dict = result.projection.model_dump(mode="json")
    assert stored_run.current_projection == result_proj_dict


# ---------------------------------------------------------------------------
# Task004 EC-3: Seq numbers contiguous within a run
# ---------------------------------------------------------------------------


def test_Task004_EC_3_test_seq_numbers_contiguous(runner_env):
    """Task004 EC-3 test_seq_numbers_contiguous"""
    runner, run_repo, event_repo, review_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)
    events = event_repo.list_by_run(result.run.run_id)

    seqs = [e.seq for e in events]
    assert seqs == list(range(1, len(events) + 1))


# ---------------------------------------------------------------------------
# Task004 ERR-1: submit_review on completed run raises
# ---------------------------------------------------------------------------


def test_Task004_ERR_1_test_submit_review_on_completed_run_raises(runner_env):
    """Task004 ERR-1 test_submit_review_on_completed_run_raises"""
    runner, run_repo, event_repo, review_repo = runner_env

    result = runner.start_run(HAPPY_PATH_JSON, RunMode.LIVE)
    assert result.projection.status == RunStatus.COMPLETED

    with pytest.raises(RunnerError, match="not in review_required status"):
        runner.submit_review(result.run.run_id, ReviewDecision.APPROVE)
