"""SQLite Review Repository implementation (Feature 005)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.core.enums import ReviewDecision, ReviewStatus
from app.core.models import ReviewTask
from app.db.models import ReviewRow
from app.db.repositories.base import AbstractReviewRepository


def _ensure_utc(dt: datetime) -> datetime:
    """Re-attach UTC tzinfo if SQLite stripped it."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteReviewRepository(AbstractReviewRepository):
    """Concrete review repository backed by SQLite via SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _to_row(self, review: ReviewTask) -> ReviewRow:
        return ReviewRow(
            review_id=review.review_id,
            run_id=review.run_id,
            status=review.status.value,
            decision=review.decision.value if review.decision is not None else None,
            reviewed_at=review.reviewed_at,
        )

    def _from_row(self, row: ReviewRow) -> ReviewTask:
        return ReviewTask(
            review_id=row.review_id,
            run_id=row.run_id,
            status=ReviewStatus(row.status),
            decision=ReviewDecision(row.decision) if row.decision is not None else None,
            reviewed_at=_ensure_utc(row.reviewed_at) if row.reviewed_at is not None else None,
        )

    def create(self, review: ReviewTask) -> ReviewTask:
        with self._session_factory() as session:
            row = self._to_row(review)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._from_row(row)

    def update_decision(
        self, review_id: str, decision: ReviewDecision, reviewed_at: datetime
    ) -> ReviewTask:
        with self._session_factory() as session:
            row = session.get(ReviewRow, review_id)
            if row is None:
                raise ValueError(f"Review not found: {review_id}")
            row.decision = decision.value
            row.reviewed_at = reviewed_at
            row.status = ReviewStatus.COMPLETED.value
            session.commit()
            session.refresh(row)
            return self._from_row(row)

    def get_by_run(self, run_id: str) -> ReviewTask | None:
        with self._session_factory() as session:
            row = (
                session.query(ReviewRow)
                .filter(ReviewRow.run_id == run_id)
                .first()
            )
            if row is None:
                return None
            return self._from_row(row)
