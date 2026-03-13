"""SQLite Receipt Repository implementation (Feature 013)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.core.receipts.models import Receipt
from app.db.models import ReceiptRow
from app.db.repositories.base import AbstractReceiptRepository


def _ensure_utc(dt: datetime) -> datetime:
    """Re-attach UTC tzinfo if SQLite stripped it."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteReceiptRepository(AbstractReceiptRepository):
    """Concrete receipt repository backed by SQLite via SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _to_row(self, receipt: Receipt) -> ReceiptRow:
        return ReceiptRow(
            receipt_id=receipt.receipt_id,
            run_id=receipt.run_id,
            raw_response=receipt.raw_response,
            prompt_version=receipt.prompt_version,
            model_id=receipt.model_id,
            created_at=receipt.created_at,
        )

    def _from_row(self, row: ReceiptRow) -> Receipt:
        return Receipt(
            receipt_id=row.receipt_id,
            run_id=row.run_id,
            raw_response=row.raw_response,
            prompt_version=row.prompt_version,
            model_id=row.model_id,
            created_at=_ensure_utc(row.created_at),
        )

    def create(self, receipt: Receipt) -> Receipt:
        with self._session_factory() as session:
            row = self._to_row(receipt)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._from_row(row)

    def get_by_run(self, run_id: str) -> Receipt | None:
        with self._session_factory() as session:
            row = (
                session.query(ReceiptRow)
                .filter(ReceiptRow.run_id == run_id)
                .first()
            )
            if row is None:
                return None
            return self._from_row(row)
