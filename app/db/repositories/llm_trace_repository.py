"""SQLite LLM trace repository implementation."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import LLMTraceRow
from app.db.repositories.base import AbstractLLMTraceRepository
from app.observability.llm_traces import LLMTrace


def _ensure_utc(dt: datetime) -> datetime:
    """Re-attach UTC tzinfo if SQLite stripped it."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteLLMTraceRepository(AbstractLLMTraceRepository):
    """Concrete LLM trace repository backed by SQLite via SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _to_row(self, trace: LLMTrace) -> LLMTraceRow:
        return LLMTraceRow(
            trace_id=trace.trace_id,
            run_id=trace.run_id,
            workflow_type=trace.workflow_type,
            prompt_version=trace.prompt_version,
            model_id=trace.model_id,
            latency_ms=trace.latency_ms,
            input_chars=trace.input_chars,
            response_chars=trace.response_chars,
            parse_success=trace.parse_success,
            parse_error=trace.parse_error,
            policy_status=trace.policy_status,
            reason_codes_json=trace.reason_codes,
            error_type=trace.error_type,
            error_message=trace.error_message,
            created_at=trace.created_at,
        )

    def _from_row(self, row: LLMTraceRow) -> LLMTrace:
        return LLMTrace(
            trace_id=row.trace_id,
            run_id=row.run_id,
            workflow_type=row.workflow_type,
            prompt_version=row.prompt_version,
            model_id=row.model_id,
            latency_ms=row.latency_ms,
            input_chars=row.input_chars,
            response_chars=row.response_chars,
            parse_success=row.parse_success,
            parse_error=row.parse_error,
            policy_status=row.policy_status,
            reason_codes=row.reason_codes_json,
            error_type=row.error_type,
            error_message=row.error_message,
            created_at=_ensure_utc(row.created_at),
        )

    def create(self, trace: LLMTrace) -> LLMTrace:
        with self._session_factory() as session:
            row = self._to_row(trace)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._from_row(row)

    def list_recent(self, limit: int = 100) -> list[LLMTrace]:
        with self._session_factory() as session:
            rows = (
                session.query(LLMTraceRow)
                .order_by(LLMTraceRow.created_at.desc(), LLMTraceRow.trace_id)
                .limit(limit)
                .all()
            )
            return [self._from_row(row) for row in rows]

    def list_by_run(self, run_id: str) -> list[LLMTrace]:
        with self._session_factory() as session:
            rows = (
                session.query(LLMTraceRow)
                .filter(LLMTraceRow.run_id == run_id)
                .order_by(LLMTraceRow.created_at, LLMTraceRow.trace_id)
                .all()
            )
            return [self._from_row(row) for row in rows]
