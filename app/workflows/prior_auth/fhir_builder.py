"""FHIR R4 resource builder for prior authorization workflows.

Builds Claim (use: preauthorization), ClaimResponse, and Bundle resources
from normalized workflow data. Uses fhir.resources Pydantic models for
schema-compliant resource generation.
"""

from datetime import date

from fhir.resources.R4B.bundle import Bundle, BundleEntry
from fhir.resources.R4B.claim import (
    Claim,
    ClaimDiagnosis,
    ClaimInsurance,
    ClaimItem,
    ClaimProcedure,
)
from fhir.resources.R4B.claimresponse import (
    ClaimResponse,
    ClaimResponseProcessNote,
)
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.reference import Reference

from app.core.models import ValidatedDecision
from app.workflows.prior_auth.schema import NormalizedFields

ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10-cm"
CPT_SYSTEM = "http://www.ama-assn.org/go/cpt"
CLAIM_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/claim-type"
PROCESS_PRIORITY_SYSTEM = "http://terminology.hl7.org/CodeSystem/processpriority"
OUTCOME_MAP = {
    "approved": "complete",
    "review_required": "queued",
    "rejected": "error",
}
PRIORITY_MAP = {
    "routine": "normal",
    "urgent": "stat",
    "emergent": "stat",
}


def build_prior_auth_claim(normalized: NormalizedFields) -> Claim:
    """Build a FHIR R4 Claim with use='preauthorization'."""
    diagnoses = [
        ClaimDiagnosis(
            sequence=i + 1,
            diagnosisCodeableConcept=CodeableConcept(
                coding=[Coding(system=ICD10_SYSTEM, code=dx.code, display=dx.display)],
            ),
        )
        for i, dx in enumerate(normalized.diagnoses)
        if dx.code
    ]

    procedures = [
        ClaimProcedure(
            sequence=i + 1,
            procedureCodeableConcept=CodeableConcept(
                coding=[Coding(system=CPT_SYSTEM, code=proc.code, display=proc.display)],
            ),
        )
        for i, proc in enumerate(normalized.procedures)
        if proc.code
    ]

    items = [
        ClaimItem(
            sequence=i + 1,
            productOrService=CodeableConcept(
                coding=[Coding(system=CPT_SYSTEM, code=proc.code, display=proc.display)],
            ),
            servicedDate=normalized.service_date or None,
            quantity={"value": proc.quantity or 1},
        )
        for i, proc in enumerate(normalized.procedures)
        if proc.code
    ]

    priority_code = PRIORITY_MAP.get(normalized.urgency, "normal")

    return Claim(
        status="active",
        type=CodeableConcept(
            coding=[Coding(system=CLAIM_TYPE_SYSTEM, code="professional")],
        ),
        use="preauthorization",
        patient=Reference(reference=f"Patient/{normalized.patient_id}"),
        created=date.today().isoformat(),
        provider=Reference(
            reference=f"Practitioner/{normalized.provider_npi or 'unknown'}",
            display=normalized.provider_name,
        ),
        insurer=Reference(
            reference=f"Organization/{normalized.payer_id or 'unknown'}",
            display=normalized.payer_name,
        ),
        priority=CodeableConcept(
            coding=[Coding(system=PROCESS_PRIORITY_SYSTEM, code=priority_code)],
        ),
        insurance=[
            ClaimInsurance(
                sequence=1,
                focal=True,
                coverage=Reference(
                    reference=f"Coverage/{normalized.payer_id or 'unknown'}",
                    display=normalized.payer_name,
                ),
            ),
        ],
        diagnosis=diagnoses or None,
        procedure=procedures or None,
        item=items or None,
        supportingInfo=None,
    )


def build_claim_response(
    claim: Claim,
    decision: ValidatedDecision,
) -> ClaimResponse:
    """Build a FHIR R4 ClaimResponse from a policy decision."""
    outcome = OUTCOME_MAP.get(decision.status, "error")

    disposition_parts = []
    if decision.status == "approved":
        disposition_parts.append("Prior authorization approved.")
    elif decision.status == "review_required":
        disposition_parts.append("Prior authorization pending clinical review.")
    else:
        disposition_parts.append("Prior authorization denied.")

    if decision.reason_codes:
        disposition_parts.append(f"Reason: {', '.join(str(r) for r in decision.reason_codes)}.")

    process_notes = [
        ClaimResponseProcessNote(
            number=i + 1,
            text=str(code),
        )
        for i, code in enumerate(decision.reason_codes)
    ]

    return ClaimResponse(
        status="active",
        type=CodeableConcept(
            coding=[Coding(system=CLAIM_TYPE_SYSTEM, code="professional")],
        ),
        use="preauthorization",
        patient=claim.patient,
        created=date.today().isoformat(),
        insurer=claim.insurer or Reference(reference="Organization/unknown"),
        outcome=outcome,
        disposition=" ".join(disposition_parts),
        processNote=process_notes or None,
    )


def bundle_resources(claim: Claim, response: ClaimResponse) -> Bundle:
    """Wrap claim and response in a FHIR Bundle (type: collection)."""
    return Bundle(
        type="collection",
        entry=[
            BundleEntry(resource=claim),
            BundleEntry(resource=response),
        ],
    )


def build_prior_auth_bundle(
    normalized: NormalizedFields,
    decision: ValidatedDecision,
) -> dict:
    """Build a complete FHIR prior auth bundle and return as dict.

    Convenience function that chains claim → response → bundle.
    """
    claim = build_prior_auth_claim(normalized)
    response = build_claim_response(claim, decision)
    bundle = bundle_resources(claim, response)
    return bundle.model_dump(exclude_none=True, mode="json")
