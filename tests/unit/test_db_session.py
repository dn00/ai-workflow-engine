"""Unit tests for DB session management + init + exports."""

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import ArgumentError

from app.db.session import get_engine, get_session_factory, init_db

# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestGetEngineSqlite:
    def test_returns_engine_instance(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        assert isinstance(engine, Engine)

    def test_engine_can_connect(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1


class TestInitDbCreatesTables:
    def test_creates_all_tables(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        init_db(engine)
        table_names = sorted(inspect(engine).get_table_names())
        assert table_names == [
            "artifacts",
            "events",
            "llm_traces",
            "receipts",
            "retrieval_traces",
            "reviews",
            "runs",
        ]


class TestSessionFactoryWorks:
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


class TestInitDbIdempotent:
    def test_calling_init_db_twice_does_not_raise(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        init_db(engine)
        init_db(engine)  # second call should not raise
        table_names = sorted(inspect(engine).get_table_names())
        assert table_names == [
            "artifacts",
            "events",
            "llm_traces",
            "receipts",
            "retrieval_traces",
            "reviews",
            "runs",
        ]


class TestModuleExports:
    def test_all_public_symbols_importable_from_app_db(self) -> None:
        from app.db import (
            ArtifactRow,
            Base,
            EventRow,
            LLMTraceRow,
            RetrievalTraceRow,
            ReviewRow,
            RunRow,
            get_engine,
            get_session_factory,
            init_db,
        )

        # Verify they are the actual symbols, not None
        assert Base is not None
        assert ArtifactRow is not None
        assert RunRow is not None
        assert EventRow is not None
        assert LLMTraceRow is not None
        assert RetrievalTraceRow is not None
        assert ReviewRow is not None
        assert get_engine is not None
        assert get_session_factory is not None
        assert init_db is not None


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestGetEngineInvalidUrl:
    def test_malformed_url_raises(self) -> None:
        with pytest.raises(ArgumentError):
            get_engine("not-a-valid-url")
