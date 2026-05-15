"""Hard validation rules for prior authorization proposals."""

import datetime

from pydantic import BaseModel

from app.workflows.prior_auth.allowlist import is_valid_cpt, is_valid_icd10, is_valid_npi
from app.workflows.prior_auth.schema import NormalizedFields, Proposal


class ValidationResult(BaseModel):
    """Result of hard validation."""

    is_valid: bool
    errors: list[str]


def validate_proposal(
    proposal: Proposal,
    normalized: NormalizedFields,
) -> ValidationResult:
    """Validate required prior authorization facts before policy evaluation."""
    errors: list[str] = []

    if proposal.request_type != "prior_auth":
        errors.append("unsupported_request_type")
    if not normalized.patient_id:
        errors.append("missing_patient_id")
    if not normalized.provider_name:
        errors.append("missing_provider_name")
    if normalized.provider_npi and not is_valid_npi(normalized.provider_npi):
        errors.append("invalid_npi_format")
    if not normalized.payer_name:
        errors.append("missing_payer")
    if not normalized.diagnoses:
        errors.append("missing_diagnoses")
    if not normalized.procedures:
        errors.append("missing_procedures")

    for i, dx in enumerate(normalized.diagnoses):
        if dx.code and not is_valid_icd10(dx.code):
            errors.append(f"invalid_icd10_code_{i}")

    for i, proc in enumerate(normalized.procedures):
        if proc.code and not is_valid_cpt(proc.code):
            errors.append(f"invalid_cpt_code_{i}")

    if not normalized.service_date:
        errors.append("missing_service_date")
    elif normalized.service_date:
        try:
            parsed_date = datetime.date.fromisoformat(normalized.service_date)
            if parsed_date < datetime.date.today():
                errors.append("service_date_in_past")
        except ValueError:
            errors.append("malformed_date")

    return ValidationResult(is_valid=not errors, errors=errors)
