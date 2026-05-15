"""Policy routing for prior authorization workflows."""

from app.core.models import ValidatedDecision
from app.workflows.prior_auth.allowlist import classify_payer, classify_procedure
from app.workflows.prior_auth.schema import NormalizedFields, Proposal
from app.workflows.prior_auth.validate import ValidationResult


def evaluate_policy(
    proposal: Proposal,
    normalized: NormalizedFields,
    validation_result: ValidationResult,
    policy_version: str = "1.0",
) -> ValidatedDecision:
    """Route prior authorization requests using deterministic clinical policy rules."""
    normalized_dict = normalized.model_dump()

    if not validation_result.is_valid:
        return ValidatedDecision(
            status="rejected",
            reason_codes=list(validation_result.errors),
            normalized_fields=normalized_dict,
            allowed_actions=[],
        )

    reason_codes: list[str] = []

    # Classify each procedure
    proc_classifications = [
        classify_procedure(proc.code) for proc in normalized.procedures if proc.code
    ]

    # Emergent bypass — approve immediately
    if normalized.urgency == "emergent":
        return ValidatedDecision(
            status="approved",
            reason_codes=["emergent_bypass"],
            normalized_fields=normalized_dict,
            allowed_actions=["create_simulated_approval_task"],
        )

    # Always-review procedures
    if "always_review" in proc_classifications:
        reason_codes.append("always_review_procedure")

    # Payer classification
    payer_class = classify_payer(normalized.payer_name)
    if payer_class == "restricted":
        reason_codes.append("restricted_payer")
    elif payer_class == "unknown":
        reason_codes.append("unknown_payer")

    # High-cost procedure checks
    if "high_cost" in proc_classifications:
        if normalized.has_medical_necessity:
            reason_codes.append("high_cost_clinical_review")
        else:
            reason_codes.append("high_cost_no_necessity")

    # Code validity
    if not normalized.all_codes_valid:
        reason_codes.append("invalid_clinical_codes")

    # Medical necessity check for non-routine
    if normalized.urgency != "routine" and not normalized.has_medical_necessity:
        reason_codes.append("missing_medical_necessity")

    # Standard procedures with no triggers — auto-approve candidate
    if not reason_codes:
        all_auto_approve = all(c == "auto_approve" for c in proc_classifications)
        known_payer = payer_class in ("known", "restricted")

        if all_auto_approve and known_payer and normalized.all_codes_valid:
            return ValidatedDecision(
                status="approved",
                reason_codes=[],
                normalized_fields=normalized_dict,
                allowed_actions=["create_simulated_approval_task"],
            )

        # Standard procedures that aren't in auto-approve list
        if "standard" in proc_classifications:
            reason_codes.append("standard_clinical_review")

    if reason_codes:
        return ValidatedDecision(
            status="review_required",
            reason_codes=reason_codes,
            normalized_fields=normalized_dict,
            allowed_actions=["create_review_task"],
        )

    return ValidatedDecision(
        status="review_required",
        reason_codes=["standard_clinical_review"],
        normalized_fields=normalized_dict,
        allowed_actions=["create_review_task"],
    )
