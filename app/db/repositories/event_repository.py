"""SQLite Event Repository implementation (Feature 005)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.core.enums import ActorType, EventType
from app.core.models import Event, VersionInfo
from app.db.models import EventRow
from app.db.repositories.base import AbstractEventRepository


def _ensure_utc(dt: datetime) -> datetime:
    """Re-attach UTC tzinfo if SQLite stripped it."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteEventRepository(AbstractEventRepository):
    """Concrete event repository backed by SQLite via SQLAlchemy.

    Enforces append-only semantics (INV-3.1): no update or delete methods.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _to_row(self, event: Event) -> EventRow:
        return EventRow(
            event_id=event.event_id,
            run_id=event.run_id,
            seq=event.seq,
            event_type=event.event_type.value,
            timestamp=event.timestamp,
            actor_type=event.actor_type.value,
            payload_json=event.payload,
            version_json=event.version_info.model_dump(),
            idempotency_key=event.idempotency_key,
        )

    def _from_row(self, row: EventRow) -> Event:
        return Event(
            event_id=row.event_id,
            run_id=row.run_id,
            seq=row.seq,
            event_type=EventType(row.event_type),
            timestamp=_ensure_utc(row.timestamp),
            version_info=VersionInfo(**row.version_json),
            payload=row.payload_json,
            actor_type=ActorType(row.actor_type),
            idempotency_key=row.idempotency_key,
        )

    def append(self, event: Event) -> Event:
        with self._session_factory() as session:
            row = self._to_row(event)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._from_row(row)

    def list_by_run(self, run_id: str) -> list[Event]:
        with self._session_factory() as session:
            rows = (
                session.query(EventRow)
                .filter(EventRow.run_id == run_id)
                .order_by(EventRow.seq)
                .all()
            )
            return [self._from_row(row) for row in rows]
