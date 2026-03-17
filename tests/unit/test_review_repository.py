"""Unit tests for SQLiteReviewRepository + Module Wiring."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.enums import ReviewDecision, ReviewStatus, RunMode, RunStatus
from app.core.models import ReviewTask, Run
from app.db.models import Base
from app.db.repositories.base import enable_sqlite_fk_pragma
from app.db.repositories.review_repository import SQLiteReviewRepository
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
    return SQLiteReviewRepository(session_factory)


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


def _make_review(run_id: str = "run-001", **overrides) -> ReviewTask:
    defaults = dict(
        review_id="rev-001",
        run_id=run_id,
        status=ReviewStatus.PENDING,
        decision=None,
        reviewed_at=None,
    )
    defaults.update(overrides)
    return ReviewTask(**defaults)


# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestCreateAndRetrieveReview:
    def test_create_persists_and_returns_review(self, repo, persisted_run) -> None:
        review = _make_review()
        result = repo.create(review)
        assert result.review_id == review.review_id

        fetched = repo.get_by_run("run-001")
        assert fetched is not None
        assert fetched.review_id == review.review_id
        assert fetched.status == ReviewStatus.PENDING
        assert fetched.decision is None


class TestUpdateDecision:
    def test_update_decision_sets_fields(self, repo, persisted_run) -> None:
        review = _make_review()
        repo.create(review)
        now = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)
        updated = repo.update_decision("rev-001", ReviewDecision.APPROVE, now)
        assert updated.decision == ReviewDecision.APPROVE
        assert updated.reviewed_at == now
        assert updated.status == ReviewStatus.COMPLETED


class TestGetByRun:
    def test_get_by_run_returns_matching_review(self, repo, persisted_run) -> None:
        review = _make_review()
        repo.create(review)
        fetched = repo.get_by_run("run-001")
        assert fetched is not None
        assert fetched.run_id == "run-001"


class TestModuleReExports:
    def test_all_symbols_importable_from_repositories(self) -> None:
        from app.db.repositories import (
            AbstractEventRepository,
            AbstractReviewRepository,
            AbstractRunRepository,
            SQLiteEventRepository,
            SQLiteReviewRepository,
            SQLiteRunRepository,
            enable_sqlite_fk_pragma,
        )

        assert AbstractRunRepository is not None
        assert AbstractEventRepository is not None
        assert AbstractReviewRepository is not None
        assert SQLiteRunRepository is not None
        assert SQLiteEventRepository is not None
        assert SQLiteReviewRepository is not None
        assert enable_sqlite_fk_pragma is not None


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestGetByRunNone:
    def test_get_by_run_no_review_returns_none(self, repo) -> None:
        result = repo.get_by_run("run-with-no-review")
        assert result is None


class TestFkEnforcement:
    def test_create_review_with_nonexistent_run_raises(self, repo) -> None:
        review = _make_review(run_id="nonexistent-run")
        with pytest.raises(IntegrityError):
            repo.create(review)


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestUpdateNonexistentRaises:
    def test_update_decision_nonexistent_raises_valueerror(self, repo) -> None:
        now = datetime(2026, 6, 15, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="not found"):
            repo.update_decision("nonexistent", ReviewDecision.APPROVE, now)
