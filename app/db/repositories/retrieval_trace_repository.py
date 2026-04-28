"""SQLite retrieval trace repository implementation."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import RetrievalTraceRow
from app.db.repositories.base import AbstractRetrievalTraceRepository
from app.retrieval.traces import RetrievalTrace


def _ensure_utc(dt: datetime) -> datetime:
    """Re-attach UTC tzinfo if SQLite stripped it."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteRetrievalTraceRepository(AbstractRetrievalTraceRepository):
    """Concrete retrieval trace repository backed by SQLite via SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _to_row(self, trace: RetrievalTrace) -> RetrievalTraceRow:
        return RetrievalTraceRow(
            trace_id=trace.trace_id,
            run_id=trace.run_id,
            workflow_type=trace.workflow_type,
            query=trace.query,
            top_k=trace.top_k,
            filters_json=trace.filters,
            retrieved_chunk_ids_json=trace.retrieved_chunk_ids,
            sufficient=trace.sufficient,
            reason=trace.reason,
            created_at=trace.created_at,
        )

    def _from_row(self, row: RetrievalTraceRow) -> RetrievalTrace:
        return RetrievalTrace(
            trace_id=row.trace_id,
            run_id=row.run_id,
            workflow_type=row.workflow_type,
            query=row.query,
            top_k=row.top_k,
            filters=row.filters_json,
            retrieved_chunk_ids=row.retrieved_chunk_ids_json,
            sufficient=row.sufficient,
            reason=row.reason,
            created_at=_ensure_utc(row.created_at),
        )

    def create(self, trace: RetrievalTrace) -> RetrievalTrace:
        with self._session_factory() as session:
            row = self._to_row(trace)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._from_row(row)

    def list_by_run(self, run_id: str) -> list[RetrievalTrace]:
        with self._session_factory() as session:
            rows = (
                session.query(RetrievalTraceRow)
                .filter(RetrievalTraceRow.run_id == run_id)
                .order_by(RetrievalTraceRow.created_at, RetrievalTraceRow.trace_id)
                .all()
            )
            return [self._from_row(row) for row in rows]
