"""Public API for the app.db persistence package."""

from app.db.models import Base, EventRow, ReviewRow, RunRow
from app.db.repositories import (
    AbstractEventRepository,
    AbstractReviewRepository,
    AbstractRunRepository,
    SQLiteEventRepository,
    SQLiteReviewRepository,
    SQLiteRunRepository,
    enable_sqlite_fk_pragma,
)
from app.db.session import get_engine, get_session_factory, init_db

__all__ = [
    "Base",
    "EventRow",
    "ReviewRow",
    "RunRow",
    "get_engine",
    "get_session_factory",
    "init_db",
    "AbstractRunRepository",
    "AbstractEventRepository",
    "AbstractReviewRepository",
    "SQLiteRunRepository",
    "SQLiteEventRepository",
    "SQLiteReviewRepository",
    "enable_sqlite_fk_pragma",
]
