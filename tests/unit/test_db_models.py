"""Unit tests for SQLAlchemy ORM table models."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import JSON, DateTime, Integer, String, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    ArtifactRow,
    Base,
    EventRow,
    LLMTraceRow,
    RetrievalTraceRow,
    ReviewRow,
    RunRow,
)

# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestRunRowColumns:
    def test_run_row_has_seven_columns(self) -> None:
        table = RunRow.__table__
        assert len(table.columns) == 7

    def test_run_row_column_names_and_types(self) -> None:
        cols = {c.name: c for c in RunRow.__table__.columns}
        expected = {
            "run_id": String,
            "workflow_type": String,
            "status": String,
            "mode": String,
            "created_at": DateTime,
            "updated_at": DateTime,
            "current_projection_json": JSON,
        }
        for name, expected_type in expected.items():
            assert name in cols, f"Missing column: {name}"
            assert isinstance(cols[name].type, expected_type), (
                f"Column {name}: expected {expected_type}, got {type(cols[name].type)}"
            )

    def test_run_row_primary_key(self) -> None:
        cols = {c.name: c for c in RunRow.__table__.columns}
        assert cols["run_id"].primary_key is True


class TestEventRowColumns:
    def test_event_row_has_nine_columns(self) -> None:
        table = EventRow.__table__
        assert len(table.columns) == 9

    def test_event_row_column_names_and_types(self) -> None:
        cols = {c.name: c for c in EventRow.__table__.columns}
        expected = {
            "event_id": String,
            "run_id": String,
            "seq": Integer,
            "event_type": String,
            "timestamp": DateTime,
            "actor_type": String,
            "payload_json": JSON,
            "version_json": JSON,
            "idempotency_key": String,
        }
        for name, expected_type in expected.items():
            assert name in cols, f"Missing column: {name}"
            assert isinstance(cols[name].type, expected_type), (
                f"Column {name}: expected {expected_type}, got {type(cols[name].type)}"
            )

    def test_event_row_primary_key(self) -> None:
        cols = {c.name: c for c in EventRow.__table__.columns}
        assert cols["event_id"].primary_key is True


class TestReviewRowColumns:
    def test_review_row_has_five_columns(self) -> None:
        table = ReviewRow.__table__
        assert len(table.columns) == 5

    def test_review_row_column_names_and_types(self) -> None:
        cols = {c.name: c for c in ReviewRow.__table__.columns}
        expected = {
            "review_id": String,
            "run_id": String,
            "status": String,
            "decision": String,
            "reviewed_at": DateTime,
        }
        for name, expected_type in expected.items():
            assert name in cols, f"Missing column: {name}"
            assert isinstance(cols[name].type, expected_type), (
                f"Column {name}: expected {expected_type}, got {type(cols[name].type)}"
            )

    def test_review_row_primary_key(self) -> None:
        cols = {c.name: c for c in ReviewRow.__table__.columns}
        assert cols["review_id"].primary_key is True


class TestArtifactRowColumns:
    def test_artifact_row_has_seven_columns(self) -> None:
        table = ArtifactRow.__table__
        assert len(table.columns) == 7

    def test_artifact_row_column_names_and_types(self) -> None:
        cols = {c.name: c for c in ArtifactRow.__table__.columns}
        expected = {
            "artifact_id": String,
            "run_id": String,
            "artifact_type": String,
            "schema_version": String,
            "data_json": JSON,
            "source_receipt_id": String,
            "created_at": DateTime,
        }
        for name, expected_type in expected.items():
            assert name in cols, f"Missing column: {name}"
            assert isinstance(cols[name].type, expected_type), (
                f"Column {name}: expected {expected_type}, got {type(cols[name].type)}"
            )

    def test_artifact_row_primary_key(self) -> None:
        cols = {c.name: c for c in ArtifactRow.__table__.columns}
        assert cols["artifact_id"].primary_key is True


class TestLLMTraceRowColumns:
    def test_llm_trace_row_has_fifteen_columns(self) -> None:
        table = LLMTraceRow.__table__
        assert len(table.columns) == 15

    def test_llm_trace_row_primary_key(self) -> None:
        cols = {c.name: c for c in LLMTraceRow.__table__.columns}
        assert cols["trace_id"].primary_key is True
        assert isinstance(cols["reason_codes_json"].type, JSON)


class TestRetrievalTraceRowColumns:
    def test_retrieval_trace_row_has_ten_columns(self) -> None:
        table = RetrievalTraceRow.__table__
        assert len(table.columns) == 10

    def test_retrieval_trace_row_primary_key(self) -> None:
        cols = {c.name: c for c in RetrievalTraceRow.__table__.columns}
        assert cols["trace_id"].primary_key is True
        assert isinstance(cols["filters_json"].type, JSON)
        assert isinstance(cols["retrieved_chunk_ids_json"].type, JSON)


class TestForeignKeyConstraints:
    def test_event_row_fk_references_runs(self) -> None:
        cols = {c.name: c for c in EventRow.__table__.columns}
        fks = list(cols["run_id"].foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "runs.run_id"

    def test_review_row_fk_references_runs(self) -> None:
        cols = {c.name: c for c in ReviewRow.__table__.columns}
        fks = list(cols["run_id"].foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "runs.run_id"

    def test_artifact_row_fk_references_runs_and_receipts(self) -> None:
        cols = {c.name: c for c in ArtifactRow.__table__.columns}
        run_fks = list(cols["run_id"].foreign_keys)
        receipt_fks = list(cols["source_receipt_id"].foreign_keys)
        assert len(run_fks) == 1
        assert run_fks[0].target_fullname == "runs.run_id"
        assert len(receipt_fks) == 1
        assert receipt_fks[0].target_fullname == "receipts.receipt_id"

    def test_llm_trace_row_fk_references_runs(self) -> None:
        cols = {c.name: c for c in LLMTraceRow.__table__.columns}
        fks = list(cols["run_id"].foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "runs.run_id"

    def test_retrieval_trace_row_fk_references_runs(self) -> None:
        cols = {c.name: c for c in RetrievalTraceRow.__table__.columns}
        fks = list(cols["run_id"].foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "runs.run_id"


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestEventUniqueConstraint:
    def test_unique_constraint_on_run_id_seq(self) -> None:
        constraints = EventRow.__table__.constraints
        unique_constraints = [
            c
            for c in constraints
            if c.__class__.__name__ == "UniqueConstraint"
        ]
        assert len(unique_constraints) == 1
        uc = unique_constraints[0]
        col_names = {c.name for c in uc.columns}
        assert col_names == {"run_id", "seq"}
        assert uc.name == "uq_event_run_seq"


class TestNullableColumns:
    def test_non_nullable_columns(self) -> None:
        """PKs and required fields must NOT be nullable."""
        non_nullable = {
            "RunRow": [
                "run_id",
                "workflow_type",
                "status",
                "mode",
                "created_at",
                "updated_at",
            ],
            "EventRow": [
                "event_id",
                "run_id",
                "seq",
                "event_type",
                "timestamp",
                "actor_type",
                "payload_json",
                "version_json",
            ],
            "ReviewRow": ["review_id", "run_id", "status"],
        }
        models = {"RunRow": RunRow, "EventRow": EventRow, "ReviewRow": ReviewRow}
        for model_name, col_names in non_nullable.items():
            cols = {c.name: c for c in models[model_name].__table__.columns}
            for col_name in col_names:
                assert cols[col_name].nullable is False, (
                    f"{model_name}.{col_name} should NOT be nullable"
                )

    def test_nullable_columns(self) -> None:
        """Optional fields MUST be nullable."""
        nullable = {
            "RunRow": ["current_projection_json"],
            "EventRow": ["idempotency_key"],
            "ReviewRow": ["decision", "reviewed_at"],
        }
        models = {"RunRow": RunRow, "EventRow": EventRow, "ReviewRow": ReviewRow}
        for model_name, col_names in nullable.items():
            cols = {c.name: c for c in models[model_name].__table__.columns}
            for col_name in col_names:
                assert cols[col_name].nullable is True, (
                    f"{model_name}.{col_name} should be nullable"
                )


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestDuplicatePkRaises:
    @pytest.fixture()
    def db_session(self) -> Session:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            yield session

    def test_duplicate_run_id_raises_integrity_error(
        self, db_session: Session
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        row1 = RunRow(
            run_id="run-1",
            workflow_type="access_request",
            status="pending",
            mode="autonomous",
            created_at=now,
            updated_at=now,
        )
        row2 = RunRow(
            run_id="run-1",
            workflow_type="access_request",
            status="pending",
            mode="autonomous",
            created_at=now,
            updated_at=now,
        )
        db_session.add(row1)
        db_session.flush()
        db_session.add(row2)
        with pytest.raises(IntegrityError):
            db_session.flush()
