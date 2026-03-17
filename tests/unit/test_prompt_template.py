"""Unit tests for the access-request prompt template."""

from app.workflows.access_request.prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


FROZEN_FIELDS = [
    "request_type",
    "employee_name",
    "systems_requested",
    "manager_name",
    "start_date",
    "urgency",
    "justification",
    "recommended_action",
    "notes",
]


class TestSystemPromptContainsAllFields:
    # `test_system_prompt_contains_all_fields`
    def test_system_prompt_contains_all_fields(self):
        """AC-1: System prompt mentions all 9 frozen proposal fields."""
        for field in FROZEN_FIELDS:
            assert field in SYSTEM_PROMPT, f"Missing field: {field}"


class TestBuildUserPromptEmbedsInput:
    # `test_build_user_prompt_embeds_input`
    def test_build_user_prompt_embeds_input(self):
        """AC-2: build_user_prompt embeds the input text."""
        result = build_user_prompt("Please give John access to Salesforce")
        assert "Please give John access to Salesforce" in result


class TestPromptVersionConstant:
    # `test_prompt_version_constant`
    def test_prompt_version_constant(self):
        """AC-3: PROMPT_VERSION is '1.0'."""
        assert PROMPT_VERSION == "1.0"


class TestBuildUserPromptEmptyInput:
    # `test_build_user_prompt_empty_input`
    def test_build_user_prompt_empty_input(self):
        """EC-1: build_user_prompt with empty input returns valid prompt string."""
        result = build_user_prompt("")
        assert isinstance(result, str)
        assert len(result) > 0


class TestWorkflowBarrelExportsPrompt:
    # `test_workflow_barrel_exports_prompt`
    def test_workflow_barrel_exports_prompt(self):
        """ERR-1: Workflow barrel exports prompt symbols."""
        from app.workflows.access_request import (
            PROMPT_VERSION,
            SYSTEM_PROMPT,
            build_user_prompt,
        )

        assert PROMPT_VERSION is not None
        assert SYSTEM_PROMPT is not None
        assert callable(build_user_prompt)
