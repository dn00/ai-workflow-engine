"""Unit tests for LLM trace persistence."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.enums import RunMode, RunStatus
from app.core.models import Run
from app.db.models import Base
from app.db.repositories.base import enable_sqlite_fk_pragma
from app.db.repositories.llm_trace_repository import SQLiteLLMTraceRepository
from app.db.repositories.run_repository import SQLiteRunRepository
from app.observability.llm_traces import LLMTrace


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_fk_pragma(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture
def run_repo(session_factory):
    return SQLiteRunRepository(session_factory)


@pytest.fixture
def repo(session_factory):
    return SQLiteLLMTraceRepository(session_factory)


@pytest.fixture
def persisted_run(run_repo) -> Run:
    run = Run(
        run_id="run-001",
        workflow_type="access_request",
        status=RunStatus.RECEIVED,
        mode=RunMode.LIVE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return run_repo.create(run)


def _make_trace(run_id: str = "run-001", **overrides) -> LLMTrace:
    defaults = dict(
        trace_id="trace-001",
        run_id=run_id,
        workflow_type="access_request",
        prompt_version="1.0",
        model_id="mock-model",
        latency_ms=12,
        input_chars=20,
        response_chars=120,
        parse_success=True,
        policy_status="approved",
        reason_codes=[],
        created_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return LLMTrace(**defaults)


def test_create_persists_and_lists_trace(repo, persisted_run) -> None:
    trace = _make_trace()

    created = repo.create(trace)
    by_run = repo.list_by_run("run-001")
    recent = repo.list_recent()

    assert created.trace_id == "trace-001"
    assert by_run == [created]
    assert recent == [created]
    assert by_run[0].policy_status == "approved"
    assert by_run[0].parse_success is True


def test_list_limit_returns_recent_traces(repo, persisted_run) -> None:
    repo.create(_make_trace(trace_id="trace-001"))
    repo.create(
        _make_trace(
            trace_id="trace-002",
            created_at=datetime(2026, 3, 1, 12, 1, tzinfo=timezone.utc),
        )
    )

    traces = repo.list_recent(limit=1)

    assert [trace.trace_id for trace in traces] == ["trace-002"]


def test_list_by_run_unknown_returns_empty(repo) -> None:
    assert repo.list_by_run("missing") == []


def test_create_fk_violation_raises(repo) -> None:
    with pytest.raises(IntegrityError):
        repo.create(_make_trace(run_id="missing-run"))
