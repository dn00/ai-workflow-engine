"""Tests for access request workflow types."""

from app.core.enums import ReasonCode
from app.workflows.access_request.reason_codes import AccessRequestReasonCode
from app.workflows.access_request.schema import NormalizedFields


class TestAccessRequestReasonCodeHas6Values:
    def test_has_6_values(self) -> None:
        assert len(AccessRequestReasonCode) == 6

    def test_exact_values(self) -> None:
        expected = {
            "missing_manager_name",
            "high_urgency",
            "too_many_systems",
            "unknown_system",
            "forbidden_system",
            "manager_approval_unverified",
        }
        assert {m.value for m in AccessRequestReasonCode} == expected


class TestNormalizedFieldsInWorkflowModule:
    def test_import_and_construct(self) -> None:
        nf = NormalizedFields(
            employee_name="Jane Doe",
            systems_requested=["salesforce", "looker"],
            manager_name="Sarah Kim",
        )
        assert nf.employee_name == "Jane Doe"
        assert nf.systems_requested == ["salesforce", "looker"]
        assert nf.manager_name == "Sarah Kim"

    def test_manager_name_optional(self) -> None:
        nf = NormalizedFields(
            employee_name="Jane Doe",
            systems_requested=["salesforce"],
        )
        assert nf.manager_name is None


class TestStrValuesUnchanged:
    def test_core_malformed_date_value(self) -> None:
        assert ReasonCode.MALFORMED_DATE.value == "malformed_date"

    def test_access_request_high_urgency_value(self) -> None:
        assert AccessRequestReasonCode.HIGH_URGENCY.value == "high_urgency"
