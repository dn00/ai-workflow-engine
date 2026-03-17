"""Integration tests for DB schema roundtrip + constraints."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, EventRow, ReviewRow, RunRow


@pytest.fixture()
def db_session():
    """In-memory SQLite session with FK enforcement enabled."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()


def _make_run(run_id: str = "run-1") -> RunRow:
    now = datetime.now(tz=timezone.utc)
    return RunRow(
        run_id=run_id,
        workflow_type="access_request",
        status="pending",
        mode="autonomous",
        created_at=now,
        updated_at=now,
    )


def _make_event(run_id: str = "run-1", seq: int = 1) -> EventRow:
    now = datetime.now(tz=timezone.utc)
    return EventRow(
        event_id=f"evt-{run_id}-{seq}",
        run_id=run_id,
        seq=seq,
        event_type="proposal_submitted",
        timestamp=now,
        actor_type="system",
        payload_json={"key": "value"},
        version_json={"schema": "1.0"},
    )


# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestRunRowRoundtrip:
    def test_insert_and_query_run_row(self, db_session: Session) -> None:
        run = _make_run()
        db_session.add(run)
        db_session.commit()

        fetched = db_session.get(RunRow, "run-1")
        assert fetched is not None
        assert fetched.run_id == "run-1"
        assert fetched.workflow_type == "access_request"
        assert fetched.status == "pending"
        assert fetched.mode == "autonomous"
        assert fetched.created_at is not None
        assert fetched.updated_at is not None
        assert fetched.current_projection_json is None


class TestEventRowRoundtrip:
    def test_insert_and_query_event_row(self, db_session: Session) -> None:
        db_session.add(_make_run())
        db_session.flush()

        evt = _make_event()
        db_session.add(evt)
        db_session.commit()

        fetched = db_session.get(EventRow, "evt-run-1-1")
        assert fetched is not None
        assert fetched.run_id == "run-1"
        assert fetched.seq == 1
        assert fetched.event_type == "proposal_submitted"
        assert fetched.payload_json == {"key": "value"}
        assert fetched.version_json == {"schema": "1.0"}
        assert fetched.idempotency_key is None


class TestReviewRowRoundtrip:
    def test_insert_and_query_review_row(self, db_session: Session) -> None:
        db_session.add(_make_run())
        db_session.flush()

        review = ReviewRow(
            review_id="rev-1",
            run_id="run-1",
            status="pending",
            decision=None,
            reviewed_at=None,
        )
        db_session.add(review)
        db_session.commit()

        fetched = db_session.get(ReviewRow, "rev-1")
        assert fetched is not None
        assert fetched.run_id == "run-1"
        assert fetched.status == "pending"
        assert fetched.decision is None
        assert fetched.reviewed_at is None


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestDuplicateEventSeqFails:
    def test_duplicate_run_id_seq_raises_integrity_error(
        self, db_session: Session
    ) -> None:
        db_session.add(_make_run())
        db_session.flush()

        db_session.add(_make_event(seq=1))
        db_session.flush()

        db_session.add(_make_event(seq=1))  # duplicate (run-1, 1)
        with pytest.raises(IntegrityError):
            db_session.flush()


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestFkViolationRaises:
    def test_event_with_nonexistent_run_raises(self, db_session: Session) -> None:
        evt = _make_event(run_id="nonexistent-run")
        db_session.add(evt)
        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            db_session.flush()
