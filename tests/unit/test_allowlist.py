"""Tests for system allowlist (Feature 006, Task 002)."""

from app.workflows.access_request.allowlist import classify_system


class TestTask002AC1LowRiskSystemClassified:
    """Task002 AC-1 test_low_risk_system_classified"""

    def test_salesforce_is_low_risk(self) -> None:
        assert classify_system("salesforce") == "low_risk"

    def test_all_low_risk_systems(self) -> None:
        low_risk = [
            "salesforce", "looker", "jira", "confluence",
            "slack", "google_workspace", "github",
        ]
        for system in low_risk:
            assert classify_system(system) == "low_risk", f"{system} should be low_risk"


class TestTask002AC2ForbiddenSystemClassified:
    """Task002 AC-2 test_forbidden_system_classified"""

    def test_admin_console_is_forbidden(self) -> None:
        assert classify_system("admin_console") == "forbidden"

    def test_all_forbidden_systems(self) -> None:
        forbidden = ["admin_console", "root_access", "production_db"]
        for system in forbidden:
            assert classify_system(system) == "forbidden", f"{system} should be forbidden"


class TestTask002AC3UnknownSystemClassified:
    """Task002 AC-3 test_unknown_system_classified"""

    def test_custom_app_is_unknown(self) -> None:
        assert classify_system("my_custom_app") == "unknown"


class TestTask002AC4KnownSystemClassified:
    """Task002 AC-4 test_known_system_classified"""

    def test_aws_is_known(self) -> None:
        assert classify_system("aws") == "known"

    def test_all_known_non_low_risk_systems(self) -> None:
        known = ["aws", "azure", "gcp", "datadog"]
        for system in known:
            assert classify_system(system) == "known", f"{system} should be known"


class TestTask002EC1CaseInsensitiveClassification:
    """Task002 EC-1 test_case_insensitive_classification"""

    def test_uppercase_salesforce(self) -> None:
        assert classify_system("SALESFORCE") == "low_risk"

    def test_mixed_case(self) -> None:
        assert classify_system("Admin_Console") == "forbidden"


class TestTask002EC2WhitespaceStripped:
    """Task002 EC-2 test_whitespace_stripped"""

    def test_leading_trailing_whitespace(self) -> None:
        assert classify_system(" salesforce ") == "low_risk"


class TestTask002ERR1EmptyStringIsUnknown:
    """Task002 ERR-1 test_empty_string_is_unknown"""

    def test_empty_string(self) -> None:
        assert classify_system("") == "unknown"
