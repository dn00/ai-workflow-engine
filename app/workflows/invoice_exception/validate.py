"""Hard validation rules for invoice exception proposals."""

from pydantic import BaseModel

from app.workflows.invoice_exception.schema import NormalizedFields, Proposal


class ValidationResult(BaseModel):
    """Result of hard validation."""

    is_valid: bool
    errors: list[str]


def validate_proposal(
    proposal: Proposal,
    normalized: NormalizedFields,
) -> ValidationResult:
    """Validate required invoice exception facts before policy evaluation."""
    errors: list[str] = []

    if proposal.request_type != "invoice_exception":
        errors.append("unsupported_request_type")
    if not normalized.vendor_name:
        errors.append("missing_vendor_name")
    if not normalized.invoice_number:
        errors.append("missing_invoice_number")
    if not normalized.po_number:
        errors.append("missing_po_number")
    if normalized.invoice_amount <= 0:
        errors.append("invalid_invoice_amount")
    if normalized.po_amount <= 0:
        errors.append("invalid_po_amount")
    if not normalized.discrepancy_reason:
        errors.append("missing_discrepancy_reason")
    for index, item in enumerate(normalized.line_items):
        if item.amount is not None and item.amount < 0:
            errors.append(f"negative_line_item_amount_{index}")

    return ValidationResult(is_valid=not errors, errors=errors)
