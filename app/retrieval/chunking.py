"""Markdown/text document loading and deterministic chunking."""

import hashlib
import re
from pathlib import Path

from app.retrieval.models import Document, DocumentChunk


def load_text_document(
    path: Path,
    *,
    source_type: str,
    metadata: dict | None = None,
) -> Document:
    """Load a markdown/text document with a stable content hash."""
    text = path.read_text()
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Document(
        document_id=path.stem,
        source_name=path.name,
        source_type=source_type,
        content_hash=content_hash,
        text=text,
        metadata=metadata or {},
    )


def chunk_document(document: Document, *, max_chars: int = 900) -> list[DocumentChunk]:
    """Split a document into stable paragraph-oriented chunks."""
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", document.text)
        if paragraph.strip()
    ]

    chunks: list[DocumentChunk] = []
    current_parts: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        additional = len(paragraph) + (2 if current_parts else 0)
        if current_parts and current_len + additional > max_chars:
            chunks.append(_make_chunk(document, len(chunks), "\n\n".join(current_parts)))
            current_parts = [paragraph]
            current_len = len(paragraph)
        else:
            current_parts.append(paragraph)
            current_len += additional

    if current_parts:
        chunks.append(_make_chunk(document, len(chunks), "\n\n".join(current_parts)))

    return chunks


def _make_chunk(document: Document, index: int, text: str) -> DocumentChunk:
    chunk_hash = hashlib.sha256(
        f"{document.document_id}:{index}:{document.content_hash}".encode("utf-8")
    ).hexdigest()[:12]
    return DocumentChunk(
        chunk_id=f"{document.document_id}:{index}:{chunk_hash}",
        document_id=document.document_id,
        chunk_index=index,
        source_name=document.source_name,
        text=text,
        metadata={
            **document.metadata,
            "source_type": document.source_type,
            "content_hash": document.content_hash,
        },
    )
