"""Typed retrieval models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Source document loaded into the retrieval corpus."""

    document_id: str
    source_name: str
    source_type: str
    content_hash: str
    text: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class DocumentChunk(BaseModel):
    """Chunk derived from a source document."""

    chunk_id: str
    document_id: str
    chunk_index: int
    source_name: str
    text: str
    metadata: dict = Field(default_factory=dict)
    embedding_model: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RetrievedChunk(BaseModel):
    """Chunk returned by retrieval."""

    chunk_id: str
    document_id: str
    source_name: str
    text: str
    score: float
    metadata: dict = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """Result from a retrieval request."""

    query: str
    chunks: list[RetrievedChunk]
    sufficient: bool
    reason: str | None = None
