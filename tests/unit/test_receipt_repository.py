"""Unit tests for Receipt infrastructure."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.enums import RunMode, RunStatus
from app.core.models import Run
from app.core.receipts.models import Receipt
from app.db.models import Base
from app.db.repositories.base import enable_sqlite_fk_pragma
from app.db.repositories.receipt_repository import SQLiteReceiptRepository
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
    return SQLiteReceiptRepository(session_factory)


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


def _make_receipt(run_id: str = "run-001", **overrides) -> Receipt:
    defaults = dict(
        receipt_id="rcpt-001",
        run_id=run_id,
        raw_response='{"action": "approve"}',
        prompt_version="1.0",
        model_id=None,
        created_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Receipt(**defaults)


# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestReceiptModelDefaults:
    def test_receipt_model_defaults(self) -> None:
        receipt = Receipt(
            run_id="r-1", raw_response="...", prompt_version="1.0"
        )
        assert isinstance(receipt.receipt_id, str)
        assert len(receipt.receipt_id) > 0
        assert receipt.created_at.tzinfo is not None
        assert receipt.model_id is None


class TestReceiptRowRoundTrip:
    def test_receipt_row_round_trip(self, session_factory, persisted_run) -> None:
        from app.db.models import ReceiptRow

        receipt = _make_receipt()
        row = ReceiptRow(
            receipt_id=receipt.receipt_id,
            run_id=receipt.run_id,
            raw_response=receipt.raw_response,
            prompt_version=receipt.prompt_version,
            model_id=receipt.model_id,
            created_at=receipt.created_at,
        )
        with session_factory() as session:
            session.add(row)
            session.commit()

        with session_factory() as session:
            fetched = session.get(ReceiptRow, "rcpt-001")
            assert fetched is not None
            assert fetched.receipt_id == receipt.receipt_id
            assert fetched.run_id == receipt.run_id
            assert fetched.raw_response == receipt.raw_response
            assert fetched.prompt_version == receipt.prompt_version
            assert fetched.model_id == receipt.model_id
            assert fetched.created_at is not None


class TestCreatePersistsReceipt:
    def test_create_persists_and_returns_receipt(self, repo, persisted_run) -> None:
        receipt = _make_receipt()
        result = repo.create(receipt)
        assert result.receipt_id == receipt.receipt_id
        assert result.run_id == receipt.run_id
        assert result.raw_response == receipt.raw_response
        assert result.prompt_version == receipt.prompt_version

        fetched = repo.get_by_run("run-001")
        assert fetched is not None
        assert fetched.receipt_id == receipt.receipt_id


class TestGetByRunRetrieves:
    def test_get_by_run_retrieves(self, repo, persisted_run) -> None:
        receipt = _make_receipt()
        repo.create(receipt)
        fetched = repo.get_by_run("run-001")
        assert fetched is not None
        assert fetched.run_id == "run-001"
        assert fetched.raw_response == receipt.raw_response


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestGetByRunUnknownReturnsNone:
    def test_get_by_run_unknown_returns_none(self, repo) -> None:
        result = repo.get_by_run("nonexistent")
        assert result is None


class TestReceiptModelIdNoneRoundTrip:
    def test_receipt_model_id_none_round_trip(self, repo, persisted_run) -> None:
        receipt = _make_receipt(model_id=None)
        repo.create(receipt)
        fetched = repo.get_by_run("run-001")
        assert fetched is not None
        assert fetched.model_id is None


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestCreateFkViolationRaises:
    def test_create_fk_violation_raises(self, repo) -> None:
        receipt = _make_receipt(run_id="no-such-run")
        with pytest.raises(IntegrityError):
            repo.create(receipt)
