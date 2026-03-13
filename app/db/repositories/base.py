"""Abstract repository interfaces and FK pragma utility (Feature 005)."""

from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import Engine, event

from app.core.enums import ReviewDecision, RunStatus
from app.core.models import Event, ReviewTask, Run
from app.core.receipts.models import Receipt


class AbstractRunRepository(ABC):
    """Abstract base class for run persistence operations."""

    @abstractmethod
    def create(self, run: Run) -> Run: ...

    @abstractmethod
    def get(self, run_id: str) -> Run | None: ...

    @abstractmethod
    def update_status(
        self, run_id: str, status: RunStatus, updated_at: datetime
    ) -> Run: ...

    @abstractmethod
    def update_projection(
        self, run_id: str, projection: dict, updated_at: datetime
    ) -> Run: ...


class AbstractEventRepository(ABC):
    """Abstract base class for event persistence operations."""

    @abstractmethod
    def append(self, event: Event) -> Event: ...

    @abstractmethod
    def list_by_run(self, run_id: str) -> list[Event]: ...


class AbstractReviewRepository(ABC):
    """Abstract base class for review persistence operations."""

    @abstractmethod
    def create(self, review: ReviewTask) -> ReviewTask: ...

    @abstractmethod
    def update_decision(
        self, review_id: str, decision: ReviewDecision, reviewed_at: datetime
    ) -> ReviewTask: ...

    @abstractmethod
    def get_by_run(self, run_id: str) -> ReviewTask | None: ...


class AbstractReceiptRepository(ABC):
    """Abstract base class for receipt persistence operations."""

    @abstractmethod
    def create(self, receipt: Receipt) -> Receipt: ...

    @abstractmethod
    def get_by_run(self, run_id: str) -> Receipt | None: ...


def enable_sqlite_fk_pragma(engine: Engine) -> None:
    """Register a SQLAlchemy event listener that enables SQLite FK enforcement."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
