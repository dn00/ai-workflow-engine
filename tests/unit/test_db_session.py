"""Unit tests for DB session management + init + exports (Batch 02, Task 002)."""

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import ArgumentError

from app.db.session import get_engine, get_session_factory, init_db

# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestTask002AC1GetEngineSqlite:
    """Task002 AC-1 test_get_engine_sqlite"""

    def test_returns_engine_instance(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        assert isinstance(engine, Engine)

    def test_engine_can_connect(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1


class TestTask002AC2InitDbCreatesTables:
    """Task002 AC-2 test_init_db_creates_tables"""

    def test_creates_all_three_tables(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        init_db(engine)
        table_names = sorted(inspect(engine).get_table_names())
        assert table_names == ["events", "receipts", "reviews", "runs"]


class TestTask002AC3SessionFactoryWorks:
    """Task002 AC-3 test_session_factory_works"""

    def test_session_can_execute_query(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        init_db(engine)
        session_factory = get_session_factory(engine)
        with session_factory() as session:
            result = session.execute(text("SELECT 1"))
            assert result.scalar() == 1


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestTask002EC1InitDbIdempotent:
    """Task002 EC-1 test_init_db_idempotent"""

    def test_calling_init_db_twice_does_not_raise(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        init_db(engine)
        init_db(engine)  # second call should not raise
        table_names = sorted(inspect(engine).get_table_names())
        assert table_names == ["events", "receipts", "reviews", "runs"]


class TestTask002EC2ModuleExports:
    """Task002 EC-2 test_module_exports"""

    def test_all_public_symbols_importable_from_app_db(self) -> None:
        from app.db import (
            Base,
            EventRow,
            ReviewRow,
            RunRow,
            get_engine,
            get_session_factory,
            init_db,
        )

        # Verify they are the actual symbols, not None
        assert Base is not None
        assert RunRow is not None
        assert EventRow is not None
        assert ReviewRow is not None
        assert get_engine is not None
        assert get_session_factory is not None
        assert init_db is not None


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestTask002ERR1GetEngineInvalidUrl:
    """Task002 ERR-1 test_get_engine_invalid_url"""

    def test_malformed_url_raises(self) -> None:
        with pytest.raises(ArgumentError):
            get_engine("not-a-valid-url")
