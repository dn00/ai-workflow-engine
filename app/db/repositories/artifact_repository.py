"""SQLite Artifact Repository implementation."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.core.artifacts.models import Artifact
from app.db.models import ArtifactRow
from app.db.repositories.base import AbstractArtifactRepository


def _ensure_utc(dt: datetime) -> datetime:
    """Re-attach UTC tzinfo if SQLite stripped it."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteArtifactRepository(AbstractArtifactRepository):
    """Concrete artifact repository backed by SQLite via SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _to_row(self, artifact: Artifact) -> ArtifactRow:
        return ArtifactRow(
            artifact_id=artifact.artifact_id,
            run_id=artifact.run_id,
            artifact_type=artifact.artifact_type,
            schema_version=artifact.schema_version,
            data_json=artifact.data,
            source_receipt_id=artifact.source_receipt_id,
            created_at=artifact.created_at,
        )

    def _from_row(self, row: ArtifactRow) -> Artifact:
        return Artifact(
            artifact_id=row.artifact_id,
            run_id=row.run_id,
            artifact_type=row.artifact_type,
            schema_version=row.schema_version,
            data=row.data_json,
            source_receipt_id=row.source_receipt_id,
            created_at=_ensure_utc(row.created_at),
        )

    def create(self, artifact: Artifact) -> Artifact:
        with self._session_factory() as session:
            row = self._to_row(artifact)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._from_row(row)

    def list_by_run(self, run_id: str) -> list[Artifact]:
        with self._session_factory() as session:
            rows = (
                session.query(ArtifactRow)
                .filter(ArtifactRow.run_id == run_id)
                .order_by(ArtifactRow.created_at, ArtifactRow.artifact_id)
                .all()
            )
            return [self._from_row(row) for row in rows]
