"""Field normalizer for the invoice_intake workflow.

Transforms raw Proposal fields into clean, canonical NormalizedFields.
"""

import re

from app.workflows.invoice_intake.schema import LineItem, NormalizedFields, Proposal


def _clean(value: str | None) -> str:
    """Strip and normalize whitespace. None -> empty string."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.strip())


def normalize_proposal(proposal: Proposal) -> NormalizedFields:
    """Normalize invoice proposal fields into canonical form."""
    vendor_name = _clean(proposal.vendor_name)
    invoice_number = _clean(proposal.invoice_number)

    currency = (proposal.currency or "USD").upper().strip()

    raw_items = proposal.line_items or []
    line_items: list[LineItem] = []
    for item in raw_items:
        line_items.append(LineItem(
            description=_clean(item.description) or None,
            quantity=item.quantity,
            unit_price=item.unit_price,
            amount=item.amount,
        ))

    total = proposal.total or 0.0

    return NormalizedFields(
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        currency=currency,
        line_items=line_items,
        total=total,
    )
