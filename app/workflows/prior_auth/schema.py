"""Schemas for the prior_auth workflow.

The LLM proposal is untrusted input: fields are optional at parse time, then
validation decides whether the workflow can proceed.
"""

from pydantic import BaseModel, Field


class Diagnosis(BaseModel):
    """A diagnosis extracted from clinical documentation."""

    code: str | None = None
    display: str | None = None
    rank: str | None = None


class Procedure(BaseModel):
    """A procedure or service being requested for authorization."""

    code: str | None = None
    display: str | None = None
    quantity: int | None = None


class Proposal(BaseModel):
    """LLM-generated proposal for a prior authorization request."""

    request_type: str | None = None
    patient_id: str | None = None
    provider_name: str | None = None
    provider_npi: str | None = None
    payer_name: str | None = None
    payer_id: str | None = None
    diagnoses: list[Diagnosis] | None = None
    procedures: list[Procedure] | None = None
    service_date: str | None = None
    urgency: str | None = None
    clinical_justification: str | None = None
    prior_treatments: list[str] | None = None
    notes: list[str] | None = None


class ReviewPacket(BaseModel):
    """Human-readable review packet for clinical reviewers."""

    summary: str
    findings: list[str] = Field(default_factory=list)
    fhir_claim_preview: dict = Field(default_factory=dict)


class NormalizedFields(BaseModel):
    """Normalized prior authorization facts and computed analysis."""

    patient_id: str
    provider_name: str
    provider_npi: str
    payer_name: str
    payer_id: str
    diagnoses: list[Diagnosis]
    procedures: list[Procedure]
    service_date: str
    urgency: str
    clinical_justification: str
    prior_treatments: list[str]
    primary_diagnosis: Diagnosis | None = None
    all_codes_valid: bool = False
    has_medical_necessity: bool = False
    review_packet: ReviewPacket = Field(default_factory=lambda: ReviewPacket(summary=""))
