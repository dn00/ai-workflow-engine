"""Tests for system allowlist."""

from app.workflows.access_request.allowlist import classify_system


class TestLowRiskSystemClassified:
    def test_salesforce_is_low_risk(self) -> None:
        assert classify_system("salesforce") == "low_risk"

    def test_all_low_risk_systems(self) -> None:
        low_risk = [
            "salesforce", "looker", "jira", "confluence",
            "slack", "google_workspace", "github",
        ]
        for system in low_risk:
            assert classify_system(system) == "low_risk", f"{system} should be low_risk"


class TestForbiddenSystemClassified:
    def test_admin_console_is_forbidden(self) -> None:
        assert classify_system("admin_console") == "forbidden"

    def test_all_forbidden_systems(self) -> None:
        forbidden = ["admin_console", "root_access", "production_db"]
        for system in forbidden:
            assert classify_system(system) == "forbidden", f"{system} should be forbidden"


class TestUnknownSystemClassified:
    def test_custom_app_is_unknown(self) -> None:
        assert classify_system("my_custom_app") == "unknown"


class TestKnownSystemClassified:
    def test_aws_is_known(self) -> None:
        assert classify_system("aws") == "known"

    def test_all_known_non_low_risk_systems(self) -> None:
        known = ["aws", "azure", "gcp", "datadog"]
        for system in known:
            assert classify_system(system) == "known", f"{system} should be known"


class TestCaseInsensitiveClassification:
    def test_uppercase_salesforce(self) -> None:
        assert classify_system("SALESFORCE") == "low_risk"

    def test_mixed_case(self) -> None:
        assert classify_system("Admin_Console") == "forbidden"


class TestWhitespaceStripped:
    def test_leading_trailing_whitespace(self) -> None:
        assert classify_system(" salesforce ") == "low_risk"


class TestEmptyStringIsUnknown:
    def test_empty_string(self) -> None:
        assert classify_system("") == "unknown"
