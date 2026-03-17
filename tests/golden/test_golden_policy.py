"""Golden tests for policy pipeline."""

import json
from pathlib import Path

from app.workflows.access_request import (
    evaluate_policy,
    normalize_proposal,
    parse_proposal,
    validate_proposal,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a golden fixture JSON file."""
    path = FIXTURES_DIR / name
    return json.loads(path.read_text())


def _run_pipeline(data: dict):
    """Run full parse→normalize→validate→policy pipeline."""
    parse_result = parse_proposal(json.dumps(data))
    assert parse_result.success is True
    assert parse_result.proposal is not None

    normalized = normalize_proposal(parse_result.proposal)
    validation = validate_proposal(parse_result.proposal, normalized)
    return evaluate_policy(parse_result.proposal, normalized, validation)


class TestGoldenAutoApprove:
    def test_golden_auto_approve(self) -> None:
        fixture = _load_fixture("auto_approve.json")
        decision = _run_pipeline(fixture["input"])
        expected = fixture["expected_decision"]

        assert decision.status == expected["status"]
        assert decision.reason_codes == expected["reason_codes"]
        assert decision.allowed_actions == expected["allowed_actions"]

    def test_golden_review_required(self) -> None:
        fixture = _load_fixture("review_required.json")
        decision = _run_pipeline(fixture["input"])
        expected = fixture["expected_decision"]

        assert decision.status == expected["status"]
        assert set(decision.reason_codes) == set(expected["reason_codes"])
        assert decision.allowed_actions == expected["allowed_actions"]

    def test_golden_rejected_forbidden(self) -> None:
        fixture = _load_fixture("rejected_forbidden.json")
        decision = _run_pipeline(fixture["input"])
        expected = fixture["expected_decision"]

        assert decision.status == expected["status"]
        assert set(decision.reason_codes) == set(expected["reason_codes"])
        assert decision.allowed_actions == expected["allowed_actions"]


class TestGoldenMalformedProposal:
    def test_golden_malformed_proposal(self) -> None:
        fixture = _load_fixture("malformed_proposal.json")
        parse_result = parse_proposal(fixture["input_raw"])
        expected = fixture["expected_parse"]

        assert parse_result.success is expected["success"]
        assert parse_result.proposal is expected["proposal"]
        assert expected["error_contains"] in parse_result.error
