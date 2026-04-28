"""Normalizer for invoice exception proposals."""

import re

from app.workflows.invoice_exception.schema import (
    LineItem,
    NormalizedFields,
    Proposal,
    ReviewPacket,
)


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.strip())


def _money(value: float | None) -> float:
    return round(float(value or 0.0), 2)


def _overage_percent(invoice_amount: float, po_amount: float) -> float:
    if po_amount <= 0:
        return 0.0
    return round(((invoice_amount - po_amount) / po_amount) * 100, 2)


def _review_packet(
    vendor_name: str,
    invoice_number: str,
    invoice_amount: float,
    po_amount: float,
    overage_amount: float,
    overage_percent: float,
    discrepancy_reason: str,
    cited_evidence_ids: list[str],
) -> ReviewPacket:
    summary = (
        f"Invoice {invoice_number} from {vendor_name} is "
        f"${invoice_amount:,.2f} against PO ${po_amount:,.2f}, "
        f"an overage of ${overage_amount:,.2f} ({overage_percent:.2f}%)."
    )
    findings = [
        f"Stated discrepancy reason: {discrepancy_reason or 'not provided'}.",
    ]
    if cited_evidence_ids:
        findings.append(f"Evidence cited: {', '.join(cited_evidence_ids)}.")
    else:
        findings.append("No policy or vendor evidence was cited.")

    return ReviewPacket(
        summary=summary,
        findings=findings,
        cited_evidence_ids=cited_evidence_ids,
    )


def normalize_proposal(proposal: Proposal) -> NormalizedFields:
    """Normalize invoice exception fields and compute overage facts."""
    vendor_name = _clean(proposal.vendor_name)
    invoice_number = _clean(proposal.invoice_number)
    po_number = _clean(proposal.po_number)
    currency = (proposal.currency or "USD").upper().strip()
    invoice_amount = _money(proposal.invoice_amount)
    po_amount = _money(proposal.po_amount)
    overage_amount = round(invoice_amount - po_amount, 2)
    overage_percent = _overage_percent(invoice_amount, po_amount)
    discrepancy_reason = _clean(proposal.discrepancy_reason)
    cited_evidence_ids = [
        _clean(evidence_id)
        for evidence_id in (proposal.cited_evidence_ids or [])
        if _clean(evidence_id)
    ]
    line_items = [
        LineItem(description=_clean(item.description) or None, amount=item.amount)
        for item in (proposal.line_items or [])
    ]

    return NormalizedFields(
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        po_number=po_number,
        currency=currency,
        invoice_amount=invoice_amount,
        po_amount=po_amount,
        overage_amount=overage_amount,
        overage_percent=overage_percent,
        discrepancy_reason=discrepancy_reason,
        line_items=line_items,
        cited_evidence_ids=cited_evidence_ids,
        review_packet=_review_packet(
            vendor_name,
            invoice_number,
            invoice_amount,
            po_amount,
            overage_amount,
            overage_percent,
            discrepancy_reason,
            cited_evidence_ids,
        ),
    )
