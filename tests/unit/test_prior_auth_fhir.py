"""Tests for FHIR R4 resource generation from prior auth workflow data."""

import json

import pytest

from app.core.models import ValidatedDecision
from app.workflows.prior_auth.fhir_builder import (
    build_claim_response,
    build_prior_auth_bundle,
    build_prior_auth_claim,
    bundle_resources,
)
from app.workflows.prior_auth.normalize import normalize_proposal
from app.workflows.prior_auth.parse import parse_proposal
from app.workflows.prior_auth.policy import evaluate_policy
from app.workflows.prior_auth.validate import validate_proposal


def _normalized(**overrides):
    data = {
        "request_type": "prior_auth",
        "patient_id": "PAT-001",
        "provider_name": "Dr. Sarah Chen",
        "provider_npi": "1234567890",
        "payer_name": "Aetna",
        "payer_id": "AETNA-001",
        "diagnoses": [
            {"code": "M17.11", "display": "Primary osteoarthritis, right knee", "rank": "primary"},
        ],
        "procedures": [
            {"code": "73721", "display": "MRI knee without contrast", "quantity": 1},
        ],
        "service_date": "2027-06-15",
        "urgency": "routine",
        "clinical_justification": "Knee pain failed conservative treatment.",
        "prior_treatments": ["physical therapy x 6 weeks", "naproxen 500mg BID"],
        "notes": [],
    }
    data.update(overrides)
    result = parse_proposal(json.dumps(data))
    return normalize_proposal(result.proposal)


def _decision(status="approved", reason_codes=None):
    return ValidatedDecision(
        status=status,
        reason_codes=reason_codes or [],
        normalized_fields={},
        allowed_actions=[],
    )


class TestBuildPriorAuthClaim:
    def test_claim_use_is_preauthorization(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        assert claim.use == "preauthorization"

    def test_claim_type_is_professional(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        assert claim.type.coding[0].code == "professional"

    def test_claim_patient_reference(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        assert claim.patient.reference == "Patient/PAT-001"

    def test_claim_provider_reference(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        assert claim.provider.reference == "Practitioner/1234567890"
        assert claim.provider.display == "Dr. Sarah Chen"

    def test_claim_insurer_reference(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        assert claim.insurer.reference == "Organization/AETNA-001"
        assert claim.insurer.display == "Aetna"

    def test_claim_diagnosis_icd10(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        dx = claim.diagnosis[0]
        coding = dx.diagnosisCodeableConcept.coding[0]
        assert coding.system == "http://hl7.org/fhir/sid/icd-10-cm"
        assert coding.code == "M17.11"

    def test_claim_procedure_cpt(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        proc = claim.procedure[0]
        coding = proc.procedureCodeableConcept.coding[0]
        assert coding.system == "http://www.ama-assn.org/go/cpt"
        assert coding.code == "73721"

    def test_claim_item_service_date(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        assert str(claim.item[0].servicedDate) == "2027-06-15"

    def test_claim_item_quantity(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        assert claim.item[0].quantity.value == 1

    def test_multiple_diagnoses(self) -> None:
        normalized = _normalized(diagnoses=[
            {"code": "M17.11", "display": "OA right knee", "rank": "primary"},
            {"code": "Z96.651", "display": "Presence of right artificial knee", "rank": "secondary"},
        ])
        claim = build_prior_auth_claim(normalized)
        assert len(claim.diagnosis) == 2
        assert claim.diagnosis[0].sequence == 1
        assert claim.diagnosis[1].sequence == 2

    def test_multiple_procedures(self) -> None:
        normalized = _normalized(procedures=[
            {"code": "73721", "display": "MRI knee without contrast", "quantity": 1},
            {"code": "73723", "display": "MRI knee with and without contrast", "quantity": 1},
        ])
        claim = build_prior_auth_claim(normalized)
        assert len(claim.procedure) == 2
        assert len(claim.item) == 2

    def test_emergent_priority_is_stat(self) -> None:
        claim = build_prior_auth_claim(_normalized(urgency="emergent"))
        assert claim.priority.coding[0].code == "stat"

    def test_routine_priority_is_normal(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        assert claim.priority.coding[0].code == "normal"

    def test_insurance_coverage_reference(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        assert claim.insurance[0].focal is True
        assert claim.insurance[0].coverage.reference == "Coverage/AETNA-001"

    def test_serializes_to_valid_json(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        d = claim.model_dump(exclude_none=True, mode="json")
        raw = json.dumps(d)
        parsed = json.loads(raw)
        assert parsed["resourceType"] == "Claim"
        assert parsed["use"] == "preauthorization"


class TestBuildClaimResponse:
    def test_approved_outcome_complete(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(claim, _decision("approved"))
        assert resp.outcome == "complete"
        assert "approved" in resp.disposition

    def test_review_required_outcome_queued(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(
            claim, _decision("review_required", ["high_cost_clinical_review"]),
        )
        assert resp.outcome == "queued"
        assert "pending clinical review" in resp.disposition

    def test_rejected_outcome_error(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(
            claim, _decision("rejected", ["missing_patient_id"]),
        )
        assert resp.outcome == "error"
        assert "denied" in resp.disposition

    def test_process_notes_from_reason_codes(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(
            claim, _decision("review_required", ["high_cost_clinical_review", "restricted_payer"]),
        )
        assert len(resp.processNote) == 2
        assert resp.processNote[0].text == "high_cost_clinical_review"
        assert resp.processNote[1].text == "restricted_payer"

    def test_no_process_notes_when_no_reason_codes(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(claim, _decision("approved"))
        assert resp.processNote is None

    def test_patient_matches_claim(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(claim, _decision("approved"))
        assert resp.patient.reference == claim.patient.reference

    def test_serializes_to_valid_json(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(claim, _decision("approved"))
        d = resp.model_dump(exclude_none=True, mode="json")
        raw = json.dumps(d)
        parsed = json.loads(raw)
        assert parsed["resourceType"] == "ClaimResponse"


class TestBundleResources:
    def test_bundle_type_is_collection(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(claim, _decision("approved"))
        bundle = bundle_resources(claim, resp)
        assert bundle.type == "collection"

    def test_bundle_contains_two_entries(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(claim, _decision("approved"))
        bundle = bundle_resources(claim, resp)
        assert len(bundle.entry) == 2

    def test_bundle_entry_types(self) -> None:
        claim = build_prior_auth_claim(_normalized())
        resp = build_claim_response(claim, _decision("approved"))
        bundle = bundle_resources(claim, resp)
        d = bundle.model_dump(exclude_none=True, mode="json")
        assert d["entry"][0]["resource"]["resourceType"] == "Claim"
        assert d["entry"][1]["resource"]["resourceType"] == "ClaimResponse"


class TestBuildPriorAuthBundle:
    def test_convenience_function_returns_dict(self) -> None:
        normalized = _normalized()
        decision = _decision("approved")
        bundle = build_prior_auth_bundle(normalized, decision)
        assert isinstance(bundle, dict)
        assert bundle["type"] == "collection"
        assert bundle["resourceType"] == "Bundle"

    def test_full_pipeline_approved(self) -> None:
        raw = json.dumps({
            "request_type": "prior_auth",
            "patient_id": "PAT-001",
            "provider_name": "Dr. Sarah Chen",
            "provider_npi": "1234567890",
            "payer_name": "Aetna",
            "payer_id": "AETNA-001",
            "diagnoses": [{"code": "M17.11", "display": "OA right knee", "rank": "primary"}],
            "procedures": [{"code": "73721", "display": "MRI knee", "quantity": 1}],
            "service_date": "2027-06-15",
            "urgency": "routine",
            "clinical_justification": "Failed conservative treatment.",
            "prior_treatments": ["PT x 6 weeks", "NSAIDs"],
            "notes": [],
        })
        result = parse_proposal(raw)
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)
        decision = evaluate_policy(result.proposal, normalized, validation)

        bundle = build_prior_auth_bundle(normalized, decision)
        claim = bundle["entry"][0]["resource"]
        resp = bundle["entry"][1]["resource"]

        assert claim["use"] == "preauthorization"
        assert claim["diagnosis"][0]["diagnosisCodeableConcept"]["coding"][0]["code"] == "M17.11"
        assert claim["procedure"][0]["procedureCodeableConcept"]["coding"][0]["code"] == "73721"
        assert resp["outcome"] == "complete"

    def test_full_pipeline_review_required(self) -> None:
        raw = json.dumps({
            "request_type": "prior_auth",
            "patient_id": "PAT-002",
            "provider_name": "Dr. James Park",
            "provider_npi": "9876543210",
            "payer_name": "UnitedHealthcare",
            "payer_id": "UHC-001",
            "diagnoses": [{"code": "M17.11", "display": "OA right knee", "rank": "primary"}],
            "procedures": [{"code": "27447", "display": "Total knee arthroplasty", "quantity": 1}],
            "service_date": "2027-08-01",
            "urgency": "routine",
            "clinical_justification": "Severe OA, failed conservative management.",
            "prior_treatments": ["PT", "NSAIDs", "injections"],
            "notes": [],
        })
        result = parse_proposal(raw)
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)
        decision = evaluate_policy(result.proposal, normalized, validation)

        bundle = build_prior_auth_bundle(normalized, decision)
        resp = bundle["entry"][1]["resource"]

        assert resp["outcome"] == "queued"
        assert "pending clinical review" in resp["disposition"]
