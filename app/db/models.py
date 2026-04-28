"""SQLAlchemy ORM table models for runs, events, and reviews (spec §13)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_projection_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_event_run_seq"),
    )

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actor_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    version_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)


class ReviewRow(Base):
    __tablename__ = "reviews"

    review_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReceiptRow(Base):
    __tablename__ = "receipts"

    receipt_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), nullable=False)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    artifact_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    data_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_receipt_id: Mapped[str | None] = mapped_column(
        ForeignKey("receipts.receipt_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LLMTraceRow(Base):
    __tablename__ = "llm_traces"

    trace_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    response_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parse_success: Mapped[bool | None] = mapped_column(nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_status: Mapped[str | None] = mapped_column(String, nullable=True)
    reason_codes_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
