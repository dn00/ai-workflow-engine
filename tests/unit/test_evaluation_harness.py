"""Tests for deterministic workflow eval harness."""

import json

from app.evaluation.harness import load_eval_cases, run_eval_cases
from app.evaluation.models import EvalCase, EvalExpected


def _case(
    *,
    name: str = "low risk",
    mock_response: str | None = None,
    expected: EvalExpected | None = None,
) -> EvalCase:
    return EvalCase(
        name=name,
        workflow_type="access_request",
        input_text="Give Jane access to Confluence. Manager is Bob.",
        mock_response=mock_response
        or json.dumps(
            {
                "request_type": "access_request",
                "employee_name": "Jane Doe",
                "systems_requested": ["Confluence"],
                "manager_name": "Bob Lee",
                "start_date": "2026-05-01",
                "urgency": "normal",
                "justification": "Project docs",
                "recommended_action": "approve",
                "notes": [],
            }
        ),
        expected=expected
        or EvalExpected(
            status="approved",
            fields={"systems_requested": ["confluence"]},
            reason_codes_absent=["high_urgency"],
        ),
    )


def test_run_eval_cases_passes_matching_case() -> None:
    report = run_eval_cases([_case()])

    assert report.success is True
    assert report.total == 1
    assert report.passed == 1
    assert report.results[0].field_matches == 1
    assert report.results[0].reason_code_matches == 1


def test_run_eval_cases_reports_status_mismatch() -> None:
    report = run_eval_cases([
        _case(expected=EvalExpected(status="review_required"))
    ])

    assert report.success is False
    assert report.failed == 1
    assert "status expected" in report.results[0].errors[0]


def test_run_eval_cases_reports_field_mismatch() -> None:
    report = run_eval_cases([
        _case(expected=EvalExpected(status="approved", fields={"employee_name": "Wrong"}))
    ])

    assert report.success is False
    assert "field 'employee_name'" in report.results[0].errors[0]


def test_load_eval_cases_from_directory(tmp_path) -> None:
    case_path = tmp_path / "cases.json"
    case_path.write_text(
        json.dumps(
            {
                "cases": [
                    _case(name="case one").model_dump(),
                    _case(name="case two").model_dump(),
                ]
            }
        )
    )

    cases = load_eval_cases(tmp_path)

    assert [case.name for case in cases] == ["case one", "case two"]
