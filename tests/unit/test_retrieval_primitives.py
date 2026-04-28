"""Tests for retrieval primitives."""

from pathlib import Path

from app.retrieval.chunking import chunk_document, load_text_document
from app.retrieval.context_builder import build_retrieved_context
from app.retrieval.mock_retriever import KeywordRetriever


def test_load_text_document_hashes_content(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("# Policy\n\nInvoices over 10 percent require review.")

    document = load_text_document(
        path,
        source_type="policy",
        metadata={"authority_tier": "policy"},
    )

    assert document.document_id == "policy"
    assert document.source_name == "policy.md"
    assert document.source_type == "policy"
    assert len(document.content_hash) == 64
    assert document.metadata["authority_tier"] == "policy"


def test_chunk_document_uses_stable_ids() -> None:
    path = Path("docs/policies/invoice_overage_policy.md")
    document = load_text_document(path, source_type="policy")

    chunks_one = chunk_document(document, max_chars=120)
    chunks_two = chunk_document(document, max_chars=120)

    assert len(chunks_one) >= 2
    assert [chunk.chunk_id for chunk in chunks_one] == [
        chunk.chunk_id for chunk in chunks_two
    ]
    assert chunks_one[0].metadata["source_type"] == "policy"


def test_keyword_retriever_returns_matching_chunks() -> None:
    document = load_text_document(
        Path("docs/policies/vendor_surcharge_policy.md"),
        source_type="policy",
    )
    chunks = chunk_document(document, max_chars=200)
    retriever = KeywordRetriever(chunks)

    result = retriever.retrieve("expedited shipping surcharge", top_k=2)

    assert result.sufficient is True
    assert result.chunks
    assert "expedited shipping" in result.chunks[0].text.lower()


def test_keyword_retriever_supports_metadata_filters() -> None:
    policy_doc = load_text_document(
        Path("docs/policies/invoice_overage_policy.md"),
        source_type="policy",
    )
    vendor_doc = load_text_document(
        Path("docs/vendors/acme_contract_summary.md"),
        source_type="vendor_contract",
    )
    chunks = chunk_document(policy_doc) + chunk_document(vendor_doc)
    retriever = KeywordRetriever(chunks)

    result = retriever.retrieve(
        "acme surcharge approval",
        filters={"source_type": "vendor_contract"},
    )

    assert result.sufficient is True
    assert {chunk.metadata["source_type"] for chunk in result.chunks} == {
        "vendor_contract"
    }


def test_context_builder_uses_source_labels_and_chunk_ids() -> None:
    document = load_text_document(
        Path("docs/policies/invoice_overage_policy.md"),
        source_type="policy",
    )
    retriever = KeywordRetriever(chunk_document(document))
    result = retriever.retrieve("overage greater than 10 percent")

    context = build_retrieved_context(result)

    assert result.chunks[0].chunk_id in context
    assert "Source: invoice_overage_policy.md" in context


def test_context_builder_handles_empty_result() -> None:
    document = load_text_document(
        Path("docs/policies/invoice_overage_policy.md"),
        source_type="policy",
    )
    result = KeywordRetriever(chunk_document(document)).retrieve("zzzz qqqq")

    assert build_retrieved_context(result) == "No retrieved context."
