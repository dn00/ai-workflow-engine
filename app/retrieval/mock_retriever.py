"""Deterministic keyword retriever for local tests and demos."""

import re

from app.retrieval.base import AbstractRetriever
from app.retrieval.models import DocumentChunk, RetrievalResult, RetrievedChunk


class KeywordRetriever(AbstractRetriever):
    """Simple lexical retriever over in-memory chunks."""

    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = chunks

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> RetrievalResult:
        """Return top chunks by deterministic token overlap."""
        query_tokens = _tokens(query)
        scored: list[RetrievedChunk] = []
        for chunk in self._chunks:
            if filters and not _matches_filters(chunk.metadata, filters):
                continue
            chunk_tokens = _tokens(chunk.text)
            overlap = query_tokens & chunk_tokens
            if not overlap:
                continue
            score = len(overlap) / max(len(query_tokens), 1)
            scored.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_name=chunk.source_name,
                    text=chunk.text,
                    score=round(score, 4),
                    metadata=chunk.metadata,
                )
            )

        scored.sort(key=lambda chunk: (-chunk.score, chunk.source_name, chunk.chunk_id))
        selected = scored[:top_k]
        return RetrievalResult(
            query=query,
            chunks=selected,
            sufficient=bool(selected),
            reason=None if selected else "no_keyword_overlap",
        )


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(token) > 2}


def _matches_filters(metadata: dict, filters: dict) -> bool:
    return all(metadata.get(key) == value for key, value in filters.items())
