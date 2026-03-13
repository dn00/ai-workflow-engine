"""Public API for the app.db persistence package."""

from app.db.models import Base, EventRow, ReceiptRow, ReviewRow, RunRow
from app.db.repositories import (
    AbstractEventRepository,
    AbstractReceiptRepository,
    AbstractReviewRepository,
    AbstractRunRepository,
    SQLiteEventRepository,
    SQLiteReceiptRepository,
    SQLiteReviewRepository,
    SQLiteRunRepository,
    enable_sqlite_fk_pragma,
)
from app.db.session import get_engine, get_session_factory, init_db

__all__ = [
    "Base",
    "EventRow",
    "ReceiptRow",
    "ReviewRow",
    "RunRow",
    "get_engine",
    "get_session_factory",
    "init_db",
    "AbstractRunRepository",
    "AbstractEventRepository",
    "AbstractReviewRepository",
    "AbstractReceiptRepository",
    "SQLiteRunRepository",
    "SQLiteEventRepository",
    "SQLiteReviewRepository",
    "SQLiteReceiptRepository",
    "enable_sqlite_fk_pragma",
]
