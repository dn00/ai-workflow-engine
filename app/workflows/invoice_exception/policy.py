"""Policy routing for invoice exception workflows."""

from app.core.models import ValidatedDecision
from app.workflows.invoice_exception.allowlist import classify_vendor
from app.workflows.invoice_exception.schema import NormalizedFields, Proposal
from app.workflows.invoice_exception.validate import ValidationResult

_MINOR_OVERAGE_PERCENT = 5.0
_MANAGER_REVIEW_PERCENT = 10.0
_DIRECTOR_REVIEW_PERCENT = 25.0
_SURCHARGE_TERMS = ("expedited", "weekend", "surcharge", "rush", "labor")


def _has_unsupported_surcharge(reason: str, line_descriptions: list[str]) -> bool:
    text = " ".join([reason, *line_descriptions]).lower()
    return any(term in text for term in _SURCHARGE_TERMS)


def evaluate_policy(
    proposal: Proposal,
    normalized: NormalizedFields,
    validation_result: ValidationResult,
    policy_version: str = "1.0",
) -> ValidatedDecision:
    """Route invoice exceptions using deterministic financial policy rules."""
    normalized_dict = normalized.model_dump()

    if not validation_result.is_valid:
        return ValidatedDecision(
            status="rejected",
            reason_codes=list(validation_result.errors),
            normalized_fields=normalized_dict,
            allowed_actions=[],
        )

    reason_codes: list[str] = []
    line_descriptions = [
        item.description or "" for item in normalized.line_items
    ]

    vendor_class = classify_vendor(normalized.vendor_name)
    if vendor_class == "flagged":
        return ValidatedDecision(
            status="rejected",
            reason_codes=["flagged_vendor"],
            normalized_fields=normalized_dict,
            allowed_actions=[],
        )

    if normalized.overage_amount <= 0:
        return ValidatedDecision(
            status="approved",
            reason_codes=[],
            normalized_fields=normalized_dict,
            allowed_actions=["create_simulated_approval_task"],
        )

    reason_codes.append("po_amount_exceeded")

    if vendor_class == "unknown":
        reason_codes.append("unknown_vendor")

    if not normalized.cited_evidence_ids:
        reason_codes.append("missing_evidence_citations")

    if _has_unsupported_surcharge(normalized.discrepancy_reason, line_descriptions):
        reason_codes.append("unsupported_surcharge")

    if normalized.overage_percent > _DIRECTOR_REVIEW_PERCENT:
        reason_codes.append("director_approval_required")
    elif normalized.overage_percent > _MANAGER_REVIEW_PERCENT:
        reason_codes.append("manager_approval_required")
    elif normalized.overage_percent > _MINOR_OVERAGE_PERCENT:
        reason_codes.append("ap_review_required")

    review_reasons = [
        code
        for code in reason_codes
        if code != "po_amount_exceeded"
    ]
    if review_reasons:
        return ValidatedDecision(
            status="review_required",
            reason_codes=reason_codes,
            normalized_fields=normalized_dict,
            allowed_actions=["create_review_task"],
        )

    return ValidatedDecision(
        status="approved",
        reason_codes=["minor_overage_with_evidence"],
        normalized_fields=normalized_dict,
        allowed_actions=["create_simulated_approval_task"],
    )
