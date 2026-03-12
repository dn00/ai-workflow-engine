"""Database engine, session factory, and initialization (spec §12)."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


def get_engine(url: str = "sqlite:///data/workflow.db") -> Engine:
    """Create a SQLAlchemy engine for the given database URL."""
    return create_engine(url)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine."""
    return sessionmaker(bind=engine)


def init_db(engine: Engine) -> None:
    """Create all tables defined in Base.metadata. Idempotent."""
    Base.metadata.create_all(engine)
