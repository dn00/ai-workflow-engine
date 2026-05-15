"""Integration tests for prior_auth workflow through LocalRunner.

Uses real SQLite (in-memory), real repositories, real workflow module,
and MockLLMAdapter. Verifies end-to-end event sequences, projections,
and review paths.
"""

import json

import pytest

import app.workflows  # noqa: F401 — triggers register_workflow

from app.core.enums import EventType, ReviewDecision, RunMode, RunStatus
from app.core.runners import LocalRunner
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
# Mock LLM responses
# ---------------------------------------------------------------------------

ROUTINE_IMAGING_JSON = json.dumps({
    "request_type": "prior_auth",
    "patient_id": "PAT-001",
    "provider_name": "Dr. Sarah Chen",
    "provider_npi": "1234567890",
    "payer_name": "Aetna",
    "payer_id": "AETNA-001",
    "diagnoses": [
        {"code": "M17.11", "display": "Primary osteoarthritis, right knee", "rank": "primary"},
    ],
    "procedures": [
        {"code": "73721", "display": "MRI knee without contrast", "quantity": 1},
    ],
    "service_date": "2027-06-15",
    "urgency": "routine",
    "clinical_justification": (
        "Persistent right knee pain x 6 weeks, unresponsive to "
        "physical therapy and NSAIDs. ROM limited to 90 degrees flexion."
    ),
    "prior_treatments": ["physical therapy x 6 weeks", "naproxen 500mg BID x 4 weeks"],
    "notes": [],
})

HIGH_COST_SURGERY_JSON = json.dumps({
    "request_type": "prior_auth",
    "patient_id": "PAT-002",
    "provider_name": "Dr. James Park",
    "provider_npi": "9876543210",
    "payer_name": "UnitedHealthcare",
    "payer_id": "UHC-001",
    "diagnoses": [
        {"code": "M17.11", "display": "Primary osteoarthritis, right knee", "rank": "primary"},
    ],
    "procedures": [
        {"code": "27447", "display": "Total knee arthroplasty", "quantity": 1},
    ],
    "service_date": "2027-08-01",
    "urgency": "routine",
    "clinical_justification": (
        "Severe osteoarthritis right knee, Kellgren-Lawrence grade IV. "
        "Failed 12 months of conservative management."
    ),
    "prior_treatments": [
        "physical therapy x 12 weeks",
        "NSAIDs x 6 months",
        "corticosteroid injection x 3",
        "hyaluronic acid injection",
    ],
    "notes": [],
})

EMERGENT_CARDIAC_JSON = json.dumps({
    "request_type": "prior_auth",
    "patient_id": "PAT-003",
    "provider_name": "Dr. Maria Santos",
    "provider_npi": "5555555555",
    "payer_name": "Cigna",
    "payer_id": "CIGNA-001",
    "diagnoses": [
        {"code": "I21.0", "display": "Acute ST elevation MI of anterior wall", "rank": "primary"},
    ],
    "procedures": [
        {"code": "93458", "display": "Left heart catheterization", "quantity": 1},
    ],
    "service_date": "2027-06-15",
    "urgency": "emergent",
    "clinical_justification": "STEMI, emergent cardiac catheterization required.",
    "prior_treatments": [],
    "notes": [],
})

INVALID_CODES_JSON = json.dumps({
    "request_type": "prior_auth",
    "patient_id": "PAT-004",
    "provider_name": "Dr. Test",
    "provider_npi": "1111111111",
    "payer_name": "Aetna",
    "payer_id": "AETNA-002",
    "diagnoses": [
        {"code": "BADCODE", "display": "Invalid diagnosis", "rank": "primary"},
    ],
    "procedures": [
        {"code": "ABC", "display": "Invalid procedure", "quantity": 1},
    ],
    "service_date": "2027-06-15",
    "urgency": "routine",
    "clinical_justification": "Testing invalid codes.",
    "prior_treatments": ["physical therapy"],
    "notes": [],
})


@pytest.fixture
def runner_env():
    """Set up in-memory SQLite + real repos + LocalRunner with mock LLM."""
    engine = get_engine("sqlite:///:memory:")
    enable_sqlite_fk_pragma(engine)
    init_db(engine)
    sf = get_session_factory(engine)

    run_repo = SQLiteRunRepository(sf)
    event_repo = SQLiteEventRepository(sf)
    review_repo = SQLiteReviewRepository(sf)
    effect_adapter = SimulatedEffectAdapter()
    receipt_repo = SQLiteReceiptRepository(sf)
    llm_adapter = MockLLMAdapter(responses={
        ROUTINE_IMAGING_JSON: ROUTINE_IMAGING_JSON,
        HIGH_COST_SURGERY_JSON: HIGH_COST_SURGERY_JSON,
        EMERGENT_CARDIAC_JSON: EMERGENT_CARDIAC_JSON,
        INVALID_CODES_JSON: INVALID_CODES_JSON,
    })

    runner = LocalRunner(run_repo, event_repo, review_repo, effect_adapter, llm_adapter, receipt_repo)
    return runner, run_repo, event_repo, review_repo, receipt_repo


# ---------------------------------------------------------------------------
# Auto-approve: routine imaging, known payer, valid codes
# ---------------------------------------------------------------------------

def test_routine_imaging_auto_approves(runner_env):
    runner, _run_repo, event_repo, _review_repo, _receipt_repo = runner_env

    result = runner.start_run(
        ROUTINE_IMAGING_JSON, RunMode.LIVE, workflow_type="prior_auth",
    )

    assert result.projection.status == RunStatus.COMPLETED
    events = event_repo.list_by_run(result.run.run_id)
    assert len(events) == 7

    event_types = [e.event_type for e in events]
    assert EventType.EFFECT_SIMULATED in event_types


# ---------------------------------------------------------------------------
# Review required: high-cost surgery
# ---------------------------------------------------------------------------

def test_high_cost_surgery_requires_review(runner_env):
    runner, _run_repo, event_repo, review_repo, _receipt_repo = runner_env

    result = runner.start_run(
        HIGH_COST_SURGERY_JSON, RunMode.LIVE, workflow_type="prior_auth",
    )

    assert result.projection.status == RunStatus.REVIEW_REQUIRED
    assert result.review_task is not None

    events = event_repo.list_by_run(result.run.run_id)
    event_types = [e.event_type for e in events]
    assert EventType.REVIEW_REQUESTED in event_types


# ---------------------------------------------------------------------------
# Review path: high-cost → approve → completed
# ---------------------------------------------------------------------------

def test_high_cost_review_then_approve(runner_env):
    runner, _run_repo, event_repo, _review_repo, _receipt_repo = runner_env

    result1 = runner.start_run(
        HIGH_COST_SURGERY_JSON, RunMode.LIVE, workflow_type="prior_auth",
    )
    assert result1.projection.status == RunStatus.REVIEW_REQUIRED

    result2 = runner.submit_review(result1.run.run_id, ReviewDecision.APPROVE)
    assert result2.projection.status == RunStatus.COMPLETED

    events = event_repo.list_by_run(result1.run.run_id)
    assert len(events) == 9


# ---------------------------------------------------------------------------
# Review path: high-cost → reject → completed
# ---------------------------------------------------------------------------

def test_high_cost_review_then_reject(runner_env):
    runner, _run_repo, event_repo, _review_repo, _receipt_repo = runner_env

    result1 = runner.start_run(
        HIGH_COST_SURGERY_JSON, RunMode.LIVE, workflow_type="prior_auth",
    )
    assert result1.projection.status == RunStatus.REVIEW_REQUIRED

    result2 = runner.submit_review(result1.run.run_id, ReviewDecision.REJECT)
    assert result2.projection.status == RunStatus.COMPLETED

    events = event_repo.list_by_run(result1.run.run_id)
    event_types = [e.event_type for e in events]
    assert EventType.REVIEW_REJECTED in event_types


# ---------------------------------------------------------------------------
# Emergent bypass: auto-approve regardless of other factors
# ---------------------------------------------------------------------------

def test_emergent_bypasses_to_approval(runner_env):
    runner, _run_repo, event_repo, _review_repo, _receipt_repo = runner_env

    result = runner.start_run(
        EMERGENT_CARDIAC_JSON, RunMode.LIVE, workflow_type="prior_auth",
    )

    assert result.projection.status == RunStatus.COMPLETED

    events = event_repo.list_by_run(result.run.run_id)
    event_types = [e.event_type for e in events]
    assert EventType.EFFECT_SIMULATED in event_types


# ---------------------------------------------------------------------------
# Validation failure: invalid clinical codes
# ---------------------------------------------------------------------------

def test_invalid_codes_rejected(runner_env):
    runner, _run_repo, event_repo, _review_repo, _receipt_repo = runner_env

    result = runner.start_run(
        INVALID_CODES_JSON, RunMode.LIVE, workflow_type="prior_auth",
    )

    assert result.projection.status == RunStatus.PROPOSAL_INVALID

    events = event_repo.list_by_run(result.run.run_id)
    event_types = [e.event_type for e in events]
    assert EventType.VALIDATION_FAILED in event_types


# ---------------------------------------------------------------------------
# Replay: routine imaging round-trip
# ---------------------------------------------------------------------------

def test_replay_routine_imaging(runner_env):
    runner, _run_repo, event_repo, _review_repo, _receipt_repo = runner_env

    result = runner.start_run(
        ROUTINE_IMAGING_JSON, RunMode.LIVE, workflow_type="prior_auth",
    )
    assert result.projection.status == RunStatus.COMPLETED

    replay_result = runner.replay_run(result.run.run_id)
    assert isinstance(replay_result, ReplayResult)
    assert replay_result.match is True


# ---------------------------------------------------------------------------
# DRY_RUN: no effects executed
# ---------------------------------------------------------------------------

def test_dry_run_skips_effects(runner_env):
    runner, _run_repo, event_repo, _review_repo, _receipt_repo = runner_env

    result = runner.start_run(
        ROUTINE_IMAGING_JSON, RunMode.DRY_RUN, workflow_type="prior_auth",
    )

    assert result.projection.status == RunStatus.COMPLETED

    events = event_repo.list_by_run(result.run.run_id)
    event_types = [e.event_type for e in events]
    assert EventType.EFFECT_SIMULATED not in event_types
    assert EventType.EFFECT_REQUESTED not in event_types


# ---------------------------------------------------------------------------
# Receipt stored for prior_auth runs
# ---------------------------------------------------------------------------

def test_receipt_stored(runner_env):
    runner, _run_repo, _event_repo, _review_repo, receipt_repo = runner_env

    result = runner.start_run(
        ROUTINE_IMAGING_JSON, RunMode.LIVE, workflow_type="prior_auth",
    )

    receipt = receipt_repo.get_by_run(result.run.run_id)
    assert receipt is not None
    assert receipt.raw_response == ROUTINE_IMAGING_JSON


# ---------------------------------------------------------------------------
# Seq numbers contiguous
# ---------------------------------------------------------------------------

def test_seq_numbers_contiguous(runner_env):
    runner, _run_repo, event_repo, _review_repo, _receipt_repo = runner_env

    result = runner.start_run(
        ROUTINE_IMAGING_JSON, RunMode.LIVE, workflow_type="prior_auth",
    )

    events = event_repo.list_by_run(result.run.run_id)
    seqs = [e.seq for e in events]
    assert seqs == list(range(1, len(events) + 1))
