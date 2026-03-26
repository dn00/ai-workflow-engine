"""Proposal schema and normalized fields for the invoice_intake workflow.

All Proposal fields are optional because the LLM output is untrusted input.
Validation rules enforce which fields are required for the run to proceed.
"""

from pydantic import BaseModel


class LineItem(BaseModel):
    """A single line item on an invoice."""

    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class Proposal(BaseModel):
    """LLM-generated proposal for an invoice intake."""

    request_type: str | None = None
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    line_items: list[LineItem] | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    payment_terms: str | None = None
    notes: list[str] | None = None


class NormalizedFields(BaseModel):
    """Normalized fields from invoice proposal."""

    vendor_name: str
    invoice_number: str
    currency: str
    line_items: list[LineItem]
    total: float
