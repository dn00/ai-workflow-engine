"""Tests for workflow registry validation."""

from types import SimpleNamespace

import pytest

from app.workflows.registry import register_workflow


def _valid_module():
    return SimpleNamespace(
        __name__="valid_workflow",
        parse_proposal=lambda raw: raw,
        normalize_proposal=lambda proposal: proposal,
        validate_proposal=lambda proposal, normalized: None,
        evaluate_policy=lambda proposal, normalized, validation_result, policy_version="1.0": None,
    )


def test_register_workflow_rejects_empty_type() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        register_workflow("", _valid_module())


def test_register_workflow_rejects_missing_required_callable() -> None:
    module = _valid_module()
    delattr(module, "evaluate_policy")

    with pytest.raises(ValueError, match="evaluate_policy"):
        register_workflow("missing_policy_test", module)


def test_register_workflow_rejects_non_callable_required_attribute() -> None:
    module = _valid_module()
    module.parse_proposal = "not-callable"

    with pytest.raises(ValueError, match="parse_proposal"):
        register_workflow("bad_parser_test", module)


def test_register_workflow_rejects_duplicate_type() -> None:
    workflow_type = "duplicate_test_workflow"
    register_workflow(workflow_type, _valid_module())

    with pytest.raises(ValueError, match="already registered"):
        register_workflow(workflow_type, _valid_module())
