"""Policy engine for the invoice_intake workflow.

Evaluates a validated invoice proposal and produces
approved/review_required/rejected with reason codes.
"""

from app.core.models import ValidatedDecision
from app.workflows.invoice_intake.allowlist import classify_vendor
from app.workflows.invoice_intake.schema import NormalizedFields, Proposal
from app.workflows.invoice_intake.validate import ValidationResult

_AUTO_APPROVE_THRESHOLD = 5000.0
_HIGH_VALUE_THRESHOLD = 50000.0


def evaluate_policy(
    proposal: Proposal,
    normalized: NormalizedFields,
    validation_result: ValidationResult,
    policy_version: str = "1.0",
) -> ValidatedDecision:
    """Apply policy rules to produce approve/review/reject decision."""
    normalized_dict = normalized.model_dump()

    # Rejection path: validation failed
    if not validation_result.is_valid:
        return ValidatedDecision(
            status="rejected",
            reason_codes=list(validation_result.errors),
            normalized_fields=normalized_dict,
            allowed_actions=[],
        )

    reason_codes: list[str] = []

    # P1: unknown vendor requires review
    vendor_class = classify_vendor(normalized.vendor_name)
    if vendor_class == "unknown":
        reason_codes.append("unknown_vendor")

    # P2: high-value invoices require review
    if normalized.total > _HIGH_VALUE_THRESHOLD:
        reason_codes.append("high_value_invoice")
    elif normalized.total > _AUTO_APPROVE_THRESHOLD:
        reason_codes.append("above_auto_approve_threshold")

    # P3: missing line items is suspicious
    if not normalized.line_items:
        reason_codes.append("no_line_items")

    # P4: line item total mismatch
    if normalized.line_items:
        item_sum = sum(
            item.amount for item in normalized.line_items if item.amount is not None
        )
        if item_sum > 0 and abs(item_sum - normalized.total) > 0.01:
            reason_codes.append("line_item_total_mismatch")

    if reason_codes:
        return ValidatedDecision(
            status="review_required",
            reason_codes=reason_codes,
            normalized_fields=normalized_dict,
            allowed_actions=["create_review_task"],
        )

    # Auto-approve: known vendor, reasonable amount, line items add up
    return ValidatedDecision(
        status="approved",
        reason_codes=[],
        normalized_fields=normalized_dict,
        allowed_actions=["create_simulated_approval_task"],
    )
