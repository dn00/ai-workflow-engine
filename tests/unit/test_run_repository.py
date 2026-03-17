"""Unit tests for SQLiteRunRepository."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.enums import RunMode, RunStatus
from app.core.models import Run
from app.db.models import Base
from app.db.repositories.base import enable_sqlite_fk_pragma
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
def repo(session_factory):
    return SQLiteRunRepository(session_factory)


def _make_run(**overrides) -> Run:
    defaults = dict(
        run_id="run-001",
        workflow_type="access_request",
        status=RunStatus.RECEIVED,
        mode=RunMode.LIVE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        current_projection=None,
    )
    defaults.update(overrides)
    return Run(**defaults)


# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestCreateAndRetrieveRun:
    def test_create_persists_and_returns_run(self, repo) -> None:
        run = _make_run()
        result = repo.create(run)
        assert result.run_id == run.run_id

        fetched = repo.get(run.run_id)
        assert fetched is not None
        assert fetched.run_id == run.run_id


class TestGetRunById:
    def test_get_returns_matching_run(self, repo) -> None:
        run = _make_run()
        repo.create(run)
        fetched = repo.get("run-001")
        assert fetched is not None
        assert fetched.workflow_type == "access_request"
        assert fetched.status == RunStatus.RECEIVED


class TestUpdateStatus:
    def test_update_status_changes_fields(self, repo) -> None:
        run = _make_run()
        repo.create(run)
        new_ts = datetime(2026, 6, 15, tzinfo=timezone.utc)
        updated = repo.update_status("run-001", RunStatus.VALIDATED, new_ts)
        assert updated.status == RunStatus.VALIDATED
        assert updated.updated_at == new_ts


class TestUpdateProjection:
    def test_update_projection_sets_dict(self, repo) -> None:
        run = _make_run()
        repo.create(run)
        new_ts = datetime(2026, 6, 15, tzinfo=timezone.utc)
        proj = {"key": "value", "nested": {"a": 1}}
        updated = repo.update_projection("run-001", proj, new_ts)
        assert updated.current_projection == proj
        assert updated.updated_at == new_ts


class TestRoundTripAllFields:
    def test_all_7_fields_preserved(self, repo) -> None:
        run = _make_run(
            run_id="run-rt",
            workflow_type="custom_flow",
            status=RunStatus.EFFECT_APPLIED,
            mode=RunMode.DRY_RUN,
            created_at=datetime(2025, 12, 25, 10, 30, tzinfo=timezone.utc),
            updated_at=datetime(2025, 12, 26, 11, 45, tzinfo=timezone.utc),
            current_projection={"systems": ["jira", "github"]},
        )
        repo.create(run)
        fetched = repo.get("run-rt")
        assert fetched is not None
        assert fetched.run_id == run.run_id
        assert fetched.workflow_type == run.workflow_type
        assert fetched.status == run.status
        assert fetched.mode == run.mode
        assert fetched.created_at == run.created_at
        assert fetched.updated_at == run.updated_at
        assert fetched.current_projection == run.current_projection


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestGetNonexistentReturnsNone:
    def test_get_missing_id_returns_none(self, repo) -> None:
        result = repo.get("nonexistent-id")
        assert result is None


class TestUpdateSameStatusIdempotent:
    def test_update_to_same_status_changes_timestamp(self, repo) -> None:
        run = _make_run()
        repo.create(run)
        new_ts = datetime(2026, 6, 15, tzinfo=timezone.utc)
        updated = repo.update_status("run-001", RunStatus.RECEIVED, new_ts)
        assert updated.status == RunStatus.RECEIVED
        assert updated.updated_at == new_ts


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestDuplicateRunIdRaises:
    def test_duplicate_create_raises_integrity_error(self, repo) -> None:
        run = _make_run()
        repo.create(run)
        with pytest.raises(IntegrityError):
            repo.create(run)
