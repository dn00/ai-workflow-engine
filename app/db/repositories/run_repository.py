"""SQLite Run Repository implementation (Feature 005)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.core.enums import RunMode, RunStatus
from app.core.models import Run
from app.db.models import RunRow
from app.db.repositories.base import AbstractRunRepository


def _ensure_utc(dt: datetime) -> datetime:
    """Re-attach UTC tzinfo if SQLite stripped it."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteRunRepository(AbstractRunRepository):
    """Concrete run repository backed by SQLite via SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _to_row(self, run: Run) -> RunRow:
        return RunRow(
            run_id=run.run_id,
            workflow_type=run.workflow_type,
            status=run.status.value,
            mode=run.mode.value,
            created_at=run.created_at,
            updated_at=run.updated_at,
            current_projection_json=run.current_projection,
        )

    def _from_row(self, row: RunRow) -> Run:
        return Run(
            run_id=row.run_id,
            workflow_type=row.workflow_type,
            status=RunStatus(row.status),
            mode=RunMode(row.mode),
            created_at=_ensure_utc(row.created_at),
            updated_at=_ensure_utc(row.updated_at),
            current_projection=row.current_projection_json,
        )

    def create(self, run: Run) -> Run:
        with self._session_factory() as session:
            row = self._to_row(run)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._from_row(row)

    def get(self, run_id: str) -> Run | None:
        with self._session_factory() as session:
            row = session.get(RunRow, run_id)
            if row is None:
                return None
            return self._from_row(row)

    def update_status(
        self, run_id: str, status: RunStatus, updated_at: datetime
    ) -> Run:
        with self._session_factory() as session:
            row = session.get(RunRow, run_id)
            if row is None:
                raise ValueError(f"Run not found: {run_id}")
            row.status = status.value
            row.updated_at = updated_at
            session.commit()
            session.refresh(row)
            return self._from_row(row)

    def update_projection(
        self, run_id: str, projection: dict, updated_at: datetime
    ) -> Run:
        with self._session_factory() as session:
            row = session.get(RunRow, run_id)
            if row is None:
                raise ValueError(f"Run not found: {run_id}")
            row.current_projection_json = projection
            row.updated_at = updated_at
            session.commit()
            session.refresh(row)
            return self._from_row(row)
