"""Deterministic eval harness for workflow modules.

The harness evaluates workflow behavior with mock LLM responses. It does not
mutate runtime state or call external services.
"""

import json
from pathlib import Path

from pydantic import BaseModel

import app.workflows  # noqa: F401 - trigger workflow registration
from app.evaluation.models import EvalCase
from app.workflows.registry import get_workflow


class EvalResult(BaseModel):
    """Result for one eval case."""

    name: str
    workflow_type: str
    passed: bool
    status: str | None = None
    expected_status: str
    errors: list[str] = []
    field_matches: int = 0
    field_total: int = 0
    reason_code_matches: int = 0
    reason_code_total: int = 0


class EvalReport(BaseModel):
    """Aggregate eval report."""

    total: int
    passed: int
    failed: int
    results: list[EvalResult]

    @property
    def success(self) -> bool:
        """Whether all eval cases passed."""
        return self.failed == 0


def load_eval_cases(path: Path) -> list[EvalCase]:
    """Load eval cases from all JSON files under path."""
    cases: list[EvalCase] = []
    files = [path] if path.is_file() else sorted(path.glob("*.json"))
    for file_path in files:
        raw = json.loads(file_path.read_text())
        items = raw if isinstance(raw, list) else raw.get("cases", [])
        cases.extend(EvalCase.model_validate(item) for item in items)
    return cases


def run_eval_cases(cases: list[EvalCase]) -> EvalReport:
    """Run eval cases and aggregate results."""
    results = [_run_case(case) for case in cases]
    passed = sum(1 for result in results if result.passed)
    return EvalReport(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )


def _run_case(case: EvalCase) -> EvalResult:
    errors: list[str] = []
    status: str | None = None
    field_matches = 0
    reason_code_matches = 0
    expected = case.expected

    try:
        workflow = get_workflow(case.workflow_type)
        parse_result = workflow.parse_proposal(case.mock_response)
        if not parse_result.success:
            status = "proposal_invalid"
            normalized_fields: dict = {}
            reason_codes = [parse_result.error or "parse_failed"]
        else:
            normalized = workflow.normalize_proposal(parse_result.proposal)
            validation = workflow.validate_proposal(parse_result.proposal, normalized)
            if not validation.is_valid:
                status = "proposal_invalid"
                normalized_fields = normalized.model_dump()
                reason_codes = [str(error) for error in validation.errors]
            else:
                decision = workflow.evaluate_policy(
                    parse_result.proposal,
                    normalized,
                    validation,
                )
                status = decision.status
                normalized_fields = decision.normalized_fields
                reason_codes = [str(code) for code in decision.reason_codes]

        if status != expected.status:
            errors.append(f"status expected {expected.status!r}, got {status!r}")

        for field_name, expected_value in expected.fields.items():
            actual_value = normalized_fields.get(field_name)
            if actual_value == expected_value:
                field_matches += 1
            else:
                errors.append(
                    f"field {field_name!r} expected {expected_value!r}, "
                    f"got {actual_value!r}"
                )

        for reason_code in expected.reason_codes_contains:
            if reason_code in reason_codes:
                reason_code_matches += 1
            else:
                errors.append(f"missing reason code {reason_code!r}")

        for reason_code in expected.reason_codes_absent:
            if reason_code in reason_codes:
                errors.append(f"unexpected reason code {reason_code!r}")
            else:
                reason_code_matches += 1

    except Exception as exc:  # pragma: no cover - defensive report formatting
        errors.append(f"case raised {type(exc).__name__}: {exc}")

    return EvalResult(
        name=case.name,
        workflow_type=case.workflow_type,
        passed=not errors,
        status=status,
        expected_status=expected.status,
        errors=errors,
        field_matches=field_matches,
        field_total=len(expected.fields),
        reason_code_matches=reason_code_matches,
        reason_code_total=(
            len(expected.reason_codes_contains) + len(expected.reason_codes_absent)
        ),
    )
