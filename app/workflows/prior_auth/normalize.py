"""Normalizer for prior authorization proposals."""

import re

from app.workflows.prior_auth.allowlist import is_valid_cpt, is_valid_icd10
from app.workflows.prior_auth.schema import (
    Diagnosis,
    NormalizedFields,
    Procedure,
    Proposal,
    ReviewPacket,
)


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.strip())


def _extract_primary_diagnosis(diagnoses: list[Diagnosis]) -> Diagnosis | None:
    for dx in diagnoses:
        if dx.rank and dx.rank.lower() == "primary":
            return dx
    return diagnoses[0] if diagnoses else None


def _check_all_codes_valid(
    diagnoses: list[Diagnosis], procedures: list[Procedure],
) -> bool:
    if not diagnoses or not procedures:
        return False
    for dx in diagnoses:
        if not dx.code or not is_valid_icd10(dx.code):
            return False
    for proc in procedures:
        if not proc.code or not is_valid_cpt(proc.code):
            return False
    return True


def _build_review_packet(
    patient_id: str,
    provider_name: str,
    payer_name: str,
    primary_dx: Diagnosis | None,
    procedures: list[Procedure],
    urgency: str,
    clinical_justification: str,
    prior_treatments: list[str],
    all_codes_valid: bool,
    has_medical_necessity: bool,
) -> ReviewPacket:
    proc_names = [
        f"{p.display or p.code or 'unknown'} (CPT {p.code})"
        for p in procedures
        if p.code
    ]
    dx_display = (
        f"{primary_dx.display or primary_dx.code} (ICD-10 {primary_dx.code})"
        if primary_dx and primary_dx.code
        else "no diagnosis coded"
    )

    summary = (
        f"Prior auth request for {', '.join(proc_names) or 'unknown procedure'} "
        f"for patient {patient_id}, "
        f"primary diagnosis: {dx_display}. "
        f"Payer: {payer_name}. Urgency: {urgency}."
    )

    findings: list[str] = []
    if not all_codes_valid:
        findings.append("One or more clinical codes failed format validation.")
    if has_medical_necessity:
        findings.append(
            f"Medical necessity documented: {clinical_justification[:200]}"
        )
    else:
        findings.append("Medical necessity documentation is incomplete.")
    if prior_treatments:
        findings.append(
            f"Prior treatments: {', '.join(prior_treatments)}."
        )
    else:
        findings.append("No prior/conservative treatments documented.")

    return ReviewPacket(
        summary=summary,
        findings=findings,
    )


def normalize_proposal(proposal: Proposal) -> NormalizedFields:
    """Normalize prior authorization fields and compute derived facts."""
    patient_id = _clean(proposal.patient_id)
    provider_name = _clean(proposal.provider_name)
    provider_npi = _clean(proposal.provider_npi)
    payer_name = _clean(proposal.payer_name)
    payer_id = _clean(proposal.payer_id)
    service_date = _clean(proposal.service_date)
    urgency = _clean(proposal.urgency).lower() or "routine"
    clinical_justification = _clean(proposal.clinical_justification)

    prior_treatments = [
        _clean(t) for t in (proposal.prior_treatments or []) if _clean(t)
    ]

    diagnoses = [
        Diagnosis(
            code=_clean(dx.code).upper() if dx.code else None,
            display=_clean(dx.display),
            rank=(_clean(dx.rank).lower() or None) if dx.rank else None,
        )
        for dx in (proposal.diagnoses or [])
    ]

    procedures = [
        Procedure(
            code=_clean(proc.code) if proc.code else None,
            display=_clean(proc.display),
            quantity=proc.quantity or 1,
        )
        for proc in (proposal.procedures or [])
    ]

    primary_diagnosis = _extract_primary_diagnosis(diagnoses)
    all_codes_valid = _check_all_codes_valid(diagnoses, procedures)
    has_medical_necessity = bool(clinical_justification and prior_treatments)

    review_packet = _build_review_packet(
        patient_id, provider_name, payer_name,
        primary_diagnosis, procedures, urgency,
        clinical_justification, prior_treatments,
        all_codes_valid, has_medical_necessity,
    )

    return NormalizedFields(
        patient_id=patient_id,
        provider_name=provider_name,
        provider_npi=provider_npi,
        payer_name=payer_name,
        payer_id=payer_id,
        diagnoses=diagnoses,
        procedures=procedures,
        service_date=service_date,
        urgency=urgency,
        clinical_justification=clinical_justification,
        prior_treatments=prior_treatments,
        primary_diagnosis=primary_diagnosis,
        all_codes_valid=all_codes_valid,
        has_medical_necessity=has_medical_necessity,
        review_packet=review_packet,
    )
