"""Unit tests for SQLiteEventRepository."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.enums import ActorType, EventType, RunMode, RunStatus
from app.core.models import Event, Run, VersionInfo
from app.db.models import Base
from app.db.repositories.base import enable_sqlite_fk_pragma
from app.db.repositories.event_repository import SQLiteEventRepository
from app.db.repositories.run_repository import SQLiteRunRepository


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
    return SQLiteEventRepository(session_factory)


@pytest.fixture
def persisted_run(run_repo) -> Run:
    """Create a run so FK constraints are satisfied."""
    run = Run(
        run_id="run-001",
        workflow_type="access_request",
        status=RunStatus.RECEIVED,
        mode=RunMode.LIVE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return run_repo.create(run)


def _make_event(run_id: str = "run-001", seq: int = 0, **overrides) -> Event:
    defaults = dict(
        event_id=f"evt-{run_id}-{seq}",
        run_id=run_id,
        seq=seq,
        event_type=EventType.RUN_RECEIVED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        version_info=VersionInfo(),
        payload={"action": "test"},
        actor_type=ActorType.SYSTEM,
        idempotency_key=None,
    )
    defaults.update(overrides)
    return Event(**defaults)


# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestAppendAndListEvent:
    def test_append_persists_event(self, repo, persisted_run) -> None:
        event = _make_event()
        result = repo.append(event)
        assert result.event_id == event.event_id

        events = repo.list_by_run("run-001")
        assert len(events) == 1
        assert events[0].event_id == event.event_id


class TestListByRunOrderedBySeq:
    def test_returns_events_sorted_by_seq(self, repo, persisted_run) -> None:
        repo.append(_make_event(seq=0, event_id="evt-0"))
        repo.append(_make_event(seq=2, event_id="evt-2"))
        repo.append(_make_event(seq=1, event_id="evt-1"))

        events = repo.list_by_run("run-001")
        assert [e.seq for e in events] == [0, 1, 2]


class TestRoundTripAllFields:
    def test_all_9_fields_preserved(self, repo, persisted_run) -> None:
        event = _make_event(
            event_id="evt-full",
            run_id="run-001",
            seq=0,
            event_type=EventType.PROPOSAL_GENERATED,
            timestamp=datetime(2026, 3, 15, 14, 30, tzinfo=timezone.utc),
            version_info=VersionInfo(
                proposal_schema_version="2.0",
                prompt_version="1.5",
                policy_version="3.0",
            ),
            payload={"systems": ["jira"], "nested": {"deep": True}},
            actor_type=ActorType.LLM,
            idempotency_key="idem-key-123",
        )
        repo.append(event)
        events = repo.list_by_run("run-001")
        assert len(events) == 1
        fetched = events[0]
        assert fetched.event_id == event.event_id
        assert fetched.run_id == event.run_id
        assert fetched.seq == event.seq
        assert fetched.event_type == event.event_type
        assert fetched.timestamp == event.timestamp
        assert fetched.version_info == event.version_info
        assert fetched.payload == event.payload
        assert fetched.actor_type == event.actor_type
        assert fetched.idempotency_key == event.idempotency_key


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestListEmptyReturnsEmptyList:
    def test_no_events_returns_empty_list(self, repo) -> None:
        result = repo.list_by_run("run-with-no-events")
        assert result == []


class TestSequentialSeqValues:
    def test_sequential_appends_succeed(self, repo, persisted_run) -> None:
        repo.append(_make_event(seq=0, event_id="evt-0"))
        repo.append(_make_event(seq=1, event_id="evt-1"))
        repo.append(_make_event(seq=2, event_id="evt-2"))

        events = repo.list_by_run("run-001")
        assert len(events) == 3
        assert [e.seq for e in events] == [0, 1, 2]


class TestIndependentSequencesPerRun:
    def test_different_runs_have_independent_seqs(self, repo, run_repo) -> None:
        # Create second run
        run_b = Run(
            run_id="run-002",
            workflow_type="access_request",
            status=RunStatus.RECEIVED,
            mode=RunMode.LIVE,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        run_repo.create(Run(
            run_id="run-001",
            workflow_type="access_request",
            status=RunStatus.RECEIVED,
            mode=RunMode.LIVE,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ))
        run_repo.create(run_b)

        repo.append(_make_event(run_id="run-001", seq=0, event_id="evt-a0"))
        repo.append(_make_event(run_id="run-001", seq=1, event_id="evt-a1"))
        repo.append(_make_event(run_id="run-002", seq=0, event_id="evt-b0"))
        repo.append(_make_event(run_id="run-002", seq=1, event_id="evt-b1"))

        assert len(repo.list_by_run("run-001")) == 2
        assert len(repo.list_by_run("run-002")) == 2


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestDuplicateSeqRaisesIntegrityError:
    def test_duplicate_run_seq_raises(self, repo, persisted_run) -> None:
        repo.append(_make_event(seq=0, event_id="evt-first"))
        with pytest.raises(IntegrityError):
            repo.append(_make_event(seq=0, event_id="evt-dup"))


class TestNoUpdateDeleteMethods:
    def test_no_mutation_methods_on_event_repo(self, repo) -> None:
        forbidden = ["update", "delete", "remove", "modify"]
        for method_name in forbidden:
            assert not hasattr(repo, method_name), (
                f"SQLiteEventRepository should not have '{method_name}' method"
            )
