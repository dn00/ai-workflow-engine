"""Unit tests for deterministic retrieval primitives."""

import hashlib

from app.retrieval.chunking import chunk_document, load_text_document
from app.retrieval.context_builder import build_retrieved_context
from app.retrieval.mock_retriever import KeywordRetriever
from app.retrieval.models import Document, DocumentChunk, RetrievalResult


def test_load_text_document_sets_source_fields_and_content_hash(tmp_path) -> None:
    path = tmp_path / "approval_policy.md"
    text = "# Approval Policy\n\nInvoices over 10 percent need manager review."
    path.write_text(text)

    document = load_text_document(
        path,
        source_type="policy",
        metadata={"domain": "ap"},
    )

    assert document.document_id == "approval_policy"
    assert document.source_name == "approval_policy.md"
    assert document.source_type == "policy"
    assert document.text == text
    assert document.content_hash == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert document.metadata == {"domain": "ap"}


def test_chunk_document_preserves_metadata_and_stable_chunk_ids() -> None:
    document = Document(
        document_id="invoice_overage_policy",
        source_name="invoice_overage_policy.md",
        source_type="policy",
        content_hash="hash-001",
        text="First paragraph about invoices.\n\nSecond paragraph about overages.",
        metadata={"domain": "ap"},
    )

    chunks = chunk_document(document, max_chars=40)
    repeated = chunk_document(document, max_chars=40)

    assert [chunk.chunk_id for chunk in chunks] == [
        chunk.chunk_id for chunk in repeated
    ]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert chunks[0].metadata == {
        "domain": "ap",
        "source_type": "policy",
        "content_hash": "hash-001",
    }


def test_keyword_retriever_returns_ranked_chunks_and_honors_top_k() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="policy:0",
            document_id="policy",
            chunk_index=0,
            source_name="policy.md",
            text="Invoice overage above ten percent requires manager approval.",
        ),
        DocumentChunk(
            chunk_id="contract:0",
            document_id="contract",
            chunk_index=0,
            source_name="contract.md",
            text="Approved vendors can submit invoices.",
        ),
    ]

    result = KeywordRetriever(chunks).retrieve(
        "invoice overage manager approval",
        top_k=1,
    )

    assert result.sufficient is True
    assert [chunk.chunk_id for chunk in result.chunks] == ["policy:0"]
    assert result.chunks[0].score > 0
    assert result.reason is None


def test_keyword_retriever_honors_exact_metadata_filters() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="policy:0",
            document_id="policy",
            chunk_index=0,
            source_name="policy.md",
            text="Invoice overage policy.",
            metadata={"source_type": "policy"},
        ),
        DocumentChunk(
            chunk_id="contract:0",
            document_id="contract",
            chunk_index=0,
            source_name="contract.md",
            text="Invoice overage contract exception.",
            metadata={"source_type": "contract"},
        ),
    ]

    result = KeywordRetriever(chunks).retrieve(
        "invoice overage",
        filters={"source_type": "contract"},
    )

    assert [chunk.chunk_id for chunk in result.chunks] == ["contract:0"]


def test_keyword_retriever_reports_no_overlap() -> None:
    chunk = DocumentChunk(
        chunk_id="policy:0",
        document_id="policy",
        chunk_index=0,
        source_name="policy.md",
        text="Purchase order approval policy.",
    )

    result = KeywordRetriever([chunk]).retrieve("video encoding subtitle")

    assert result.chunks == []
    assert result.sufficient is False
    assert result.reason == "no_keyword_overlap"


def test_build_retrieved_context_renders_citation_blocks() -> None:
    chunk = DocumentChunk(
        chunk_id="policy:0",
        document_id="policy",
        chunk_index=0,
        source_name="policy.md",
        text="Invoice overages need manager approval.",
    )
    result = KeywordRetriever([chunk]).retrieve("invoice manager")

    context = build_retrieved_context(result)

    assert "[policy:0] Source: policy.md Score:" in context
    assert "Invoice overages need manager approval." in context


def test_build_retrieved_context_handles_empty_results() -> None:
    context = build_retrieved_context(
        RetrievalResult(
            query="missing",
            chunks=[],
            sufficient=False,
            reason="no_keyword_overlap",
        )
    )

    assert context == "No retrieved context."
