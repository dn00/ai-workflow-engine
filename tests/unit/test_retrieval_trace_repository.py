"""Unit tests for retrieval trace persistence."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.enums import RunMode, RunStatus
from app.core.models import Run
from app.db.models import Base
from app.db.repositories.base import enable_sqlite_fk_pragma
from app.db.repositories.retrieval_trace_repository import (
    SQLiteRetrievalTraceRepository,
)
from app.db.repositories.run_repository import SQLiteRunRepository
from app.retrieval.traces import RetrievalTrace


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
    return SQLiteRetrievalTraceRepository(session_factory)


@pytest.fixture
def persisted_run(run_repo) -> Run:
    run = Run(
        run_id="run-001",
        workflow_type="invoice_exception",
        status=RunStatus.RECEIVED,
        mode=RunMode.LIVE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return run_repo.create(run)


def _make_trace(run_id: str | None = "run-001", **overrides) -> RetrievalTrace:
    defaults = dict(
        trace_id="retrieval-trace-001",
        run_id=run_id,
        workflow_type="invoice_exception",
        query="invoice overage acme expedited shipping",
        top_k=3,
        filters={"source_type": "policy"},
        retrieved_chunk_ids=["policy:0", "contract:1"],
        sufficient=True,
        reason=None,
        created_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return RetrievalTrace(**defaults)


def test_create_persists_and_lists_trace(repo, persisted_run) -> None:
    trace = _make_trace()

    created = repo.create(trace)
    by_run = repo.list_by_run("run-001")

    assert created.trace_id == "retrieval-trace-001"
    assert by_run == [created]
    assert by_run[0].filters == {"source_type": "policy"}
    assert by_run[0].retrieved_chunk_ids == ["policy:0", "contract:1"]
    assert by_run[0].sufficient is True


def test_list_by_run_orders_oldest_first(repo, persisted_run) -> None:
    repo.create(_make_trace(trace_id="retrieval-trace-002"))
    repo.create(
        _make_trace(
            trace_id="retrieval-trace-001",
            created_at=datetime(2026, 3, 1, 11, 59, tzinfo=timezone.utc),
        )
    )

    traces = repo.list_by_run("run-001")

    assert [trace.trace_id for trace in traces] == [
        "retrieval-trace-001",
        "retrieval-trace-002",
    ]


def test_create_allows_unattached_trace(repo) -> None:
    created = repo.create(_make_trace(run_id=None))

    assert created.run_id is None
    assert repo.list_by_run("run-001") == []


def test_list_by_run_unknown_returns_empty(repo) -> None:
    assert repo.list_by_run("missing") == []


def test_create_fk_violation_raises(repo) -> None:
    with pytest.raises(IntegrityError):
        repo.create(_make_trace(run_id="missing-run"))
