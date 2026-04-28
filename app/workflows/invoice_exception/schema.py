"""Schemas for the invoice_exception workflow.

The LLM proposal is untrusted input: fields are optional at parse time, then
validation decides whether the workflow can proceed.
"""

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """A line item contributing to the invoice exception."""

    description: str | None = None
    amount: float | None = None


class Proposal(BaseModel):
    """LLM-generated proposal for an invoice exception review."""

    request_type: str | None = None
    vendor_name: str | None = None
    invoice_number: str | None = None
    po_number: str | None = None
    invoice_amount: float | None = None
    po_amount: float | None = None
    currency: str | None = None
    discrepancy_reason: str | None = None
    line_items: list[LineItem] | None = None
    cited_evidence_ids: list[str] | None = None
    notes: list[str] | None = None


class ReviewPacket(BaseModel):
    """Human-readable review packet materialized as normalized data."""

    summary: str
    findings: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)


class NormalizedFields(BaseModel):
    """Normalized invoice exception facts and deterministic analysis."""

    vendor_name: str
    invoice_number: str
    po_number: str
    currency: str
    invoice_amount: float
    po_amount: float
    overage_amount: float
    overage_percent: float
    discrepancy_reason: str
    line_items: list[LineItem]
    cited_evidence_ids: list[str]
    review_packet: ReviewPacket
