"""Schema validator for the invoice_intake workflow.

Implements hard validation rules. Accumulates all errors (not fail-fast).
"""

import datetime

from pydantic import BaseModel

from app.workflows.invoice_intake.allowlist import classify_vendor
from app.workflows.invoice_intake.schema import NormalizedFields, Proposal


class ValidationResult(BaseModel):
    """Result of hard validation."""

    is_valid: bool
    errors: list[str]


def validate_proposal(
    proposal: Proposal,
    normalized: NormalizedFields,
) -> ValidationResult:
    """Apply hard validation rules for invoice intake."""
    errors: list[str] = []

    # Rule 1: request_type must be "invoice_intake"
    if proposal.request_type != "invoice_intake":
        errors.append("unsupported_request_type")

    # Rule 2: vendor_name must be present
    if not normalized.vendor_name:
        errors.append("missing_vendor_name")

    # Rule 3: invoice_number must be present
    if not normalized.invoice_number:
        errors.append("missing_invoice_number")

    # Rule 4: flagged vendors are blocked
    if normalized.vendor_name:
        classification = classify_vendor(normalized.vendor_name)
        if classification == "flagged":
            errors.append("flagged_vendor")

    # Rule 5: total must be positive
    if normalized.total <= 0:
        errors.append("invalid_total")

    # Rule 6: invoice_date must be valid ISO date if present
    if proposal.invoice_date is not None:
        try:
            datetime.date.fromisoformat(proposal.invoice_date)
        except ValueError:
            errors.append("malformed_date")

    # Rule 7: due_date must be valid ISO date if present
    if proposal.due_date is not None:
        try:
            datetime.date.fromisoformat(proposal.due_date)
        except ValueError:
            errors.append("malformed_date")

    # Rule 8: line items should have amounts
    for i, item in enumerate(normalized.line_items):
        if item.amount is not None and item.amount < 0:
            errors.append(f"negative_line_item_amount_{i}")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
