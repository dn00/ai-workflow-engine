"""Retrieval primitives for evidence-backed workflows."""

from app.retrieval.base import AbstractRetriever
from app.retrieval.chunking import chunk_document, load_text_document
from app.retrieval.context_builder import build_retrieved_context
from app.retrieval.mock_retriever import KeywordRetriever
from app.retrieval.models import Document, DocumentChunk, RetrievalResult, RetrievedChunk
from app.retrieval.traces import RetrievalTrace

__all__ = [
    "AbstractRetriever",
    "Document",
    "DocumentChunk",
    "KeywordRetriever",
    "RetrievalResult",
    "RetrievalTrace",
    "RetrievedChunk",
    "build_retrieved_context",
    "chunk_document",
    "load_text_document",
]
