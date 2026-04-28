"""Workflow-specific retrieval query helpers for invoice exceptions."""

from app.workflows.invoice_exception.schema import NormalizedFields, Proposal


def build_retrieval_query(input_text: str) -> str:
    """Build a broad retrieval query from raw user text."""
    return (
        "invoice exception purchase order overage approval vendor surcharge "
        f"{input_text}"
    )


def build_policy_query(proposal: Proposal, normalized: NormalizedFields) -> str:
    """Build a focused policy query after extraction has produced typed facts."""
    return " ".join(
        part
        for part in [
            "invoice exception policy",
            normalized.vendor_name,
            normalized.discrepancy_reason,
            f"overage {normalized.overage_percent:.2f} percent",
            " ".join(normalized.cited_evidence_ids),
        ]
        if part
    )
