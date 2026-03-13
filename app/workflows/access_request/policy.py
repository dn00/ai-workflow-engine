"""Policy engine for the access_request workflow (spec §20).

Evaluates a validated proposal and produces exactly one of
approved/review_required/rejected with reason codes and allowed actions.
"""

from app.core.enums import ReasonCode
from app.core.models import ValidatedDecision
from app.workflows.access_request.allowlist import classify_system
from app.workflows.access_request.reason_codes import AccessRequestReasonCode
from app.workflows.access_request.schema import NormalizedFields, Proposal
from app.workflows.access_request.validate import ValidationResult

_AMBIGUITY_KEYWORDS = frozenset({"ambiguous", "contradiction", "unclear", "conflicting"})

_MAX_AUTO_APPROVE_SYSTEMS = 2


def evaluate_policy(
    proposal: Proposal,
    normalized: NormalizedFields,
    validation_result: ValidationResult,
    policy_version: str = "1.0",
) -> ValidatedDecision:
    """Apply policy rules (spec §20) to produce approve/review/reject decision."""
    normalized_dict = normalized.model_dump()

    # Rejection path: validation failed — forward all errors as reason codes
    if not validation_result.is_valid:
        return ValidatedDecision(
            status="rejected",
            reason_codes=list(validation_result.errors),
            normalized_fields=normalized_dict,
            allowed_actions=[],
        )

    # Collect review triggers (accumulate all, don't short-circuit)
    reason_codes: list[str] = []

    # R2.1: missing manager
    if normalized.manager_name is None:
        reason_codes.append(AccessRequestReasonCode.MISSING_MANAGER_NAME)

    # R2.2: high urgency (case-insensitive)
    if proposal.urgency and proposal.urgency.lower() == "high":
        reason_codes.append(AccessRequestReasonCode.HIGH_URGENCY)

    # R2.3: too many systems (>2)
    if len(normalized.systems_requested) > _MAX_AUTO_APPROVE_SYSTEMS:
        reason_codes.append(AccessRequestReasonCode.TOO_MANY_SYSTEMS)

    # R2.4: any system is known but not low_risk
    for system in normalized.systems_requested:
        classification = classify_system(system)
        if classification == "known":
            reason_codes.append(AccessRequestReasonCode.MANAGER_APPROVAL_UNVERIFIED)
            break  # one trigger is enough

    # R2.5: notes ambiguity detection
    if proposal.notes:
        for note in proposal.notes:
            note_lower = note.lower()
            if any(kw in note_lower for kw in _AMBIGUITY_KEYWORDS):
                reason_codes.append(ReasonCode.AMBIGUOUS_NORMALIZATION)
                break  # one trigger is enough

    # Decision
    if reason_codes:
        return ValidatedDecision(
            status="review_required",
            reason_codes=reason_codes,
            normalized_fields=normalized_dict,
            allowed_actions=["create_review_task"],
        )

    # Auto-approve: all conditions met
    return ValidatedDecision(
        status="approved",
        reason_codes=[],
        normalized_fields=normalized_dict,
        allowed_actions=["create_simulated_approval_task"],
    )
