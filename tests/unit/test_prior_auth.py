"""Tests for prior_auth parsing, normalization, validation, policy, and allowlist."""

import json

import pytest

from app.workflows.prior_auth.allowlist import (
    classify_payer,
    classify_procedure,
    is_valid_cpt,
    is_valid_icd10,
    is_valid_npi,
)
from app.workflows.prior_auth.normalize import normalize_proposal
from app.workflows.prior_auth.parse import parse_proposal
from app.workflows.prior_auth.policy import evaluate_policy
from app.workflows.prior_auth.prompt import build_user_prompt
from app.workflows.prior_auth.validate import validate_proposal


def _proposal_json(**overrides) -> str:
    data = {
        "request_type": "prior_auth",
        "patient_id": "PAT-001",
        "provider_name": "Dr. Sarah Chen",
        "provider_npi": "1234567890",
        "payer_name": "Aetna",
        "payer_id": "AETNA-001",
        "diagnoses": [
            {
                "code": "M17.11",
                "display": "Primary osteoarthritis, right knee",
                "rank": "primary",
            }
        ],
        "procedures": [
            {
                "code": "73721",
                "display": "MRI knee without contrast",
                "quantity": 1,
            }
        ],
        "service_date": "2027-06-15",
        "urgency": "routine",
        "clinical_justification": (
            "Persistent right knee pain x 6 weeks, unresponsive to "
            "physical therapy and NSAIDs. ROM limited to 90 degrees flexion."
        ),
        "prior_treatments": [
            "physical therapy x 6 weeks",
            "naproxen 500mg BID x 4 weeks",
        ],
        "notes": [],
    }
    data.update(overrides)
    return json.dumps(data)


def _decision(**overrides):
    result = parse_proposal(_proposal_json(**overrides))
    assert result.success
    normalized = normalize_proposal(result.proposal)
    validation = validate_proposal(result.proposal, normalized)
    return evaluate_policy(result.proposal, normalized, validation)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class TestPriorAuthParser:
    def test_valid_proposal_parses(self) -> None:
        result = parse_proposal(_proposal_json())

        assert result.success is True
        assert result.proposal.patient_id == "PAT-001"
        assert result.proposal.provider_name == "Dr. Sarah Chen"
        assert len(result.proposal.diagnoses) == 1
        assert result.proposal.diagnoses[0].code == "M17.11"

    def test_strips_markdown_fences(self) -> None:
        result = parse_proposal(f"```json\n{_proposal_json()}\n```")

        assert result.success is True
        assert result.proposal.request_type == "prior_auth"

    def test_malformed_json_fails(self) -> None:
        result = parse_proposal("not json at all")

        assert result.success is False
        assert "invalid_json" in result.error

    def test_non_object_json_fails(self) -> None:
        result = parse_proposal("[1, 2, 3]")

        assert result.success is False
        assert "expected_json_object" in result.error

    def test_empty_object_parses_with_none_fields(self) -> None:
        result = parse_proposal("{}")

        assert result.success is True
        assert result.proposal.request_type is None
        assert result.proposal.diagnoses is None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

class TestPriorAuthNormalization:
    def test_normalizes_fields_and_computes_derived_facts(self) -> None:
        result = parse_proposal(_proposal_json())
        normalized = normalize_proposal(result.proposal)

        assert normalized.patient_id == "PAT-001"
        assert normalized.urgency == "routine"
        assert normalized.all_codes_valid is True
        assert normalized.has_medical_necessity is True
        assert normalized.primary_diagnosis is not None
        assert normalized.primary_diagnosis.code == "M17.11"

    def test_extracts_primary_diagnosis_by_rank(self) -> None:
        result = parse_proposal(_proposal_json(
            diagnoses=[
                {"code": "Z96.651", "display": "Presence of right artificial knee", "rank": "secondary"},
                {"code": "M17.11", "display": "Primary osteoarthritis, right knee", "rank": "primary"},
            ]
        ))
        normalized = normalize_proposal(result.proposal)

        assert normalized.primary_diagnosis.code == "M17.11"

    def test_falls_back_to_first_diagnosis_if_no_primary(self) -> None:
        result = parse_proposal(_proposal_json(
            diagnoses=[
                {"code": "M17.11", "display": "Osteoarthritis", "rank": None},
                {"code": "Z96.651", "display": "Artificial knee", "rank": None},
            ]
        ))
        normalized = normalize_proposal(result.proposal)

        assert normalized.primary_diagnosis.code == "M17.11"

    def test_defaults_urgency_to_routine(self) -> None:
        result = parse_proposal(_proposal_json(urgency=None))
        normalized = normalize_proposal(result.proposal)

        assert normalized.urgency == "routine"

    def test_defaults_empty_lists(self) -> None:
        result = parse_proposal(_proposal_json(
            diagnoses=None, procedures=None, prior_treatments=None,
        ))
        normalized = normalize_proposal(result.proposal)

        assert normalized.diagnoses == []
        assert normalized.procedures == []
        assert normalized.prior_treatments == []

    def test_medical_necessity_requires_justification_and_treatments(self) -> None:
        result = parse_proposal(_proposal_json(
            clinical_justification="Knee pain after fall.",
            prior_treatments=[],
        ))
        normalized = normalize_proposal(result.proposal)

        assert normalized.has_medical_necessity is False

    def test_invalid_codes_detected(self) -> None:
        result = parse_proposal(_proposal_json(
            diagnoses=[{"code": "INVALID", "display": "Bad code", "rank": "primary"}],
        ))
        normalized = normalize_proposal(result.proposal)

        assert normalized.all_codes_valid is False

    def test_review_packet_built(self) -> None:
        result = parse_proposal(_proposal_json())
        normalized = normalize_proposal(result.proposal)

        assert "PAT-001" in normalized.review_packet.summary
        assert "Aetna" in normalized.review_packet.summary
        assert len(normalized.review_packet.findings) > 0

    def test_cleans_whitespace(self) -> None:
        result = parse_proposal(_proposal_json(
            provider_name="  Dr.  Sarah   Chen  ",
        ))
        normalized = normalize_proposal(result.proposal)

        assert normalized.provider_name == "Dr. Sarah Chen"

    def test_procedure_quantity_defaults_to_one(self) -> None:
        result = parse_proposal(_proposal_json(
            procedures=[{"code": "73721", "display": "MRI knee", "quantity": None}],
        ))
        normalized = normalize_proposal(result.proposal)

        assert normalized.procedures[0].quantity == 1


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestPriorAuthValidation:
    def test_valid_proposal_passes(self) -> None:
        result = parse_proposal(_proposal_json())
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is True
        assert validation.errors == []

    @pytest.mark.parametrize(
        ("field", "value", "error"),
        [
            ("request_type", "access_request", "unsupported_request_type"),
            ("patient_id", None, "missing_patient_id"),
            ("provider_name", None, "missing_provider_name"),
            ("payer_name", None, "missing_payer"),
        ],
    )
    def test_required_fields(self, field: str, value, error: str) -> None:
        result = parse_proposal(_proposal_json(**{field: value}))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert error in validation.errors

    def test_missing_diagnoses(self) -> None:
        result = parse_proposal(_proposal_json(diagnoses=[]))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert "missing_diagnoses" in validation.errors

    def test_missing_procedures(self) -> None:
        result = parse_proposal(_proposal_json(procedures=[]))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert "missing_procedures" in validation.errors

    def test_invalid_npi_format(self) -> None:
        result = parse_proposal(_proposal_json(provider_npi="12345"))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert "invalid_npi_format" in validation.errors

    def test_valid_npi_passes(self) -> None:
        result = parse_proposal(_proposal_json(provider_npi="1234567890"))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert "invalid_npi_format" not in validation.errors

    def test_null_npi_passes(self) -> None:
        result = parse_proposal(_proposal_json(provider_npi=None))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert "invalid_npi_format" not in validation.errors

    def test_invalid_icd10_code(self) -> None:
        result = parse_proposal(_proposal_json(
            diagnoses=[{"code": "INVALID", "display": "Bad", "rank": "primary"}],
        ))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert "invalid_icd10_code_0" in validation.errors

    def test_invalid_cpt_code(self) -> None:
        result = parse_proposal(_proposal_json(
            procedures=[{"code": "ABC", "display": "Bad", "quantity": 1}],
        ))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert "invalid_cpt_code_0" in validation.errors

    def test_missing_service_date(self) -> None:
        result = parse_proposal(_proposal_json(service_date=None))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert "missing_service_date" in validation.errors

    def test_malformed_service_date(self) -> None:
        result = parse_proposal(_proposal_json(service_date="not-a-date"))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert "malformed_date" in validation.errors

    def test_past_service_date(self) -> None:
        result = parse_proposal(_proposal_json(service_date="2020-01-01"))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert "service_date_in_past" in validation.errors

    def test_accumulates_multiple_errors(self) -> None:
        result = parse_proposal(_proposal_json(
            patient_id=None,
            provider_name=None,
            payer_name=None,
        ))
        normalized = normalize_proposal(result.proposal)
        validation = validate_proposal(result.proposal, normalized)

        assert validation.is_valid is False
        assert len(validation.errors) >= 3


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class TestPriorAuthPolicy:
    def test_routine_imaging_known_payer_auto_approves(self) -> None:
        decision = _decision()

        assert decision.status == "approved"
        assert decision.reason_codes == []

    def test_emergent_bypasses_all_checks(self) -> None:
        decision = _decision(urgency="emergent")

        assert decision.status == "approved"
        assert "emergent_bypass" in decision.reason_codes

    def test_high_cost_with_necessity_requires_review(self) -> None:
        decision = _decision(
            procedures=[{"code": "27447", "display": "Total knee arthroplasty", "quantity": 1}],
        )

        assert decision.status == "review_required"
        assert "high_cost_clinical_review" in decision.reason_codes

    def test_high_cost_without_necessity_requires_review(self) -> None:
        decision = _decision(
            procedures=[{"code": "27447", "display": "Total knee arthroplasty", "quantity": 1}],
            prior_treatments=[],
        )

        assert decision.status == "review_required"
        assert "high_cost_no_necessity" in decision.reason_codes

    def test_always_review_procedure(self) -> None:
        decision = _decision(
            procedures=[{"code": "64999", "display": "Unlisted nervous system procedure", "quantity": 1}],
        )

        assert decision.status == "review_required"
        assert "always_review_procedure" in decision.reason_codes

    def test_restricted_payer_requires_review(self) -> None:
        decision = _decision(payer_name="Medicare")

        assert decision.status == "review_required"
        assert "restricted_payer" in decision.reason_codes

    def test_unknown_payer_requires_review(self) -> None:
        decision = _decision(payer_name="Unknown Insurance Co")

        assert decision.status == "review_required"
        assert "unknown_payer" in decision.reason_codes

    def test_invalid_codes_require_review(self) -> None:
        decision = _decision(
            diagnoses=[{"code": "BADCODE", "display": "Invalid", "rank": "primary"}],
        )

        assert decision.status == "rejected"
        assert "invalid_icd10_code_0" in decision.reason_codes

    def test_validation_failure_rejects(self) -> None:
        decision = _decision(request_type="wrong_type")

        assert decision.status == "rejected"
        assert "unsupported_request_type" in decision.reason_codes

    def test_standard_procedure_requires_review(self) -> None:
        decision = _decision(
            procedures=[{"code": "99213", "display": "Office visit", "quantity": 1}],
        )

        assert decision.status == "review_required"
        assert "standard_clinical_review" in decision.reason_codes

    def test_missing_necessity_on_urgent_requires_review(self) -> None:
        decision = _decision(
            urgency="urgent",
            prior_treatments=[],
        )

        assert decision.status == "review_required"
        assert "missing_medical_necessity" in decision.reason_codes


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

class TestPriorAuthAllowlist:
    def test_icd10_validation(self) -> None:
        assert is_valid_icd10("M17.11") is True
        assert is_valid_icd10("Z96") is True
        assert is_valid_icd10("S72.001A") is True
        assert is_valid_icd10("INVALID") is False
        assert is_valid_icd10("123.45") is False
        assert is_valid_icd10("") is False

    def test_cpt_validation(self) -> None:
        assert is_valid_cpt("73721") is True
        assert is_valid_cpt("27447") is True
        assert is_valid_cpt("1234") is False
        assert is_valid_cpt("123456") is False
        assert is_valid_cpt("ABCDE") is False

    def test_npi_validation(self) -> None:
        assert is_valid_npi("1234567890") is True
        assert is_valid_npi("12345") is False
        assert is_valid_npi("12345678901") is False
        assert is_valid_npi("abcdefghij") is False

    def test_procedure_classification(self) -> None:
        assert classify_procedure("73721") == "auto_approve"
        assert classify_procedure("27447") == "high_cost"
        assert classify_procedure("64999") == "always_review"
        assert classify_procedure("99213") == "standard"

    def test_payer_classification(self) -> None:
        assert classify_payer("Aetna") == "known"
        assert classify_payer("Medicare") == "restricted"
        assert classify_payer("CIGNA") == "known"
        assert classify_payer("Random Insurance") == "unknown"


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

class TestPriorAuthPrompt:
    def test_prompt_includes_clinical_text(self) -> None:
        prompt = build_user_prompt("Patient presents with knee pain")

        assert "Patient presents with knee pain" in prompt

    def test_prompt_includes_retrieved_context(self) -> None:
        prompt = build_user_prompt(
            "Knee pain referral",
            retrieved_context="Aetna policy: MRI requires 6 weeks conservative treatment.",
        )

        assert "Aetna policy" in prompt
        assert "Knee pain referral" in prompt

    def test_prompt_defaults_no_context(self) -> None:
        prompt = build_user_prompt("Referral note")

        assert "No payer policy context available" in prompt
