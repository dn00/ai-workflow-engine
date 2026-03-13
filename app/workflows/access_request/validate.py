"""Schema validator for the access_request workflow (spec §19).

Implements 5 hard validation rules plus forbidden-system rejection.
Accumulates all errors (not fail-fast). Does NOT make policy decisions.
"""

import datetime

from pydantic import BaseModel

from app.core.enums import ReasonCode
from app.workflows.access_request.allowlist import classify_system
from app.workflows.access_request.reason_codes import AccessRequestReasonCode
from app.workflows.access_request.schema import NormalizedFields, Proposal


class ValidationResult(BaseModel):
    """Result of hard validation against spec §19 rules."""

    is_valid: bool
    errors: list[str]


def validate_proposal(
    proposal: Proposal,
    normalized: NormalizedFields,
) -> ValidationResult:
    """Apply hard validation rules from spec §19.

    Rules checked (all accumulated, not fail-fast):
    1. request_type must be "access_request" (INV-11.1)
    2. employee_name must be present (INV-11.2)
    3. systems_requested must be non-empty (INV-11.3)
    4. All systems must be known, none forbidden (INV-11.4, INV-11.17)
    5. start_date must be valid ISO date if present (INV-11.5)
    """
    errors: list[str] = []

    # Rule 1: request_type must be "access_request"
    if proposal.request_type != "access_request":
        errors.append(ReasonCode.UNSUPPORTED_REQUEST_TYPE)

    # Rule 2: employee_name must be present
    if not normalized.employee_name:
        errors.append("missing_employee_name")

    # Rule 3: systems_requested must be non-empty
    if not normalized.systems_requested:
        errors.append("missing_systems_requested")

    # Rule 4: system classification checks
    for system in normalized.systems_requested:
        classification = classify_system(system)
        if classification == "forbidden":
            errors.append(AccessRequestReasonCode.FORBIDDEN_SYSTEM)
        elif classification == "unknown":
            errors.append(AccessRequestReasonCode.UNKNOWN_SYSTEM)

    # Rule 5: start_date must be valid ISO date if present
    if proposal.start_date is not None:
        try:
            datetime.date.fromisoformat(proposal.start_date)
        except ValueError:
            errors.append(ReasonCode.MALFORMED_DATE)

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
