"""Unit tests for artifact persistence."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.artifacts.models import Artifact
from app.core.enums import RunMode, RunStatus
from app.core.models import Run
from app.core.receipts.models import Receipt
from app.db.models import Base
from app.db.repositories.artifact_repository import SQLiteArtifactRepository
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
def receipt_repo(session_factory):
    return SQLiteReceiptRepository(session_factory)


@pytest.fixture
def repo(session_factory):
    return SQLiteArtifactRepository(session_factory)


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


@pytest.fixture
def persisted_receipt(receipt_repo, persisted_run) -> Receipt:
    receipt = Receipt(
        receipt_id="rcpt-001",
        run_id=persisted_run.run_id,
        raw_response='{"request_type": "access_request"}',
        prompt_version="1.0",
        created_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    )
    return receipt_repo.create(receipt)


def _make_artifact(run_id: str = "run-001", **overrides) -> Artifact:
    defaults = dict(
        artifact_id="artifact-001",
        run_id=run_id,
        artifact_type="access_request.proposal",
        schema_version="1.0",
        data={"request_type": "access_request", "employee_name": "Jane"},
        source_receipt_id="rcpt-001",
        created_at=datetime(2026, 3, 1, 12, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Artifact(**defaults)


def test_artifact_model_defaults() -> None:
    artifact = Artifact(
        run_id="run-1",
        artifact_type="access_request.proposal",
        data={"field": "value"},
    )
    assert artifact.artifact_id
    assert artifact.schema_version == "1.0"
    assert artifact.created_at.tzinfo is not None


def test_create_persists_and_lists_artifact(
    repo, persisted_run, persisted_receipt
) -> None:
    artifact = _make_artifact()

    created = repo.create(artifact)
    fetched = repo.list_by_run("run-001")

    assert created.artifact_id == artifact.artifact_id
    assert len(fetched) == 1
    assert fetched[0].artifact_type == "access_request.proposal"
    assert fetched[0].data["employee_name"] == "Jane"
    assert fetched[0].source_receipt_id == "rcpt-001"


def test_list_by_run_unknown_returns_empty(repo) -> None:
    assert repo.list_by_run("missing") == []


def test_create_fk_violation_raises(repo) -> None:
    artifact = _make_artifact(run_id="missing-run", source_receipt_id=None)
    with pytest.raises(IntegrityError):
        repo.create(artifact)
