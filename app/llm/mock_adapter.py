"""Mock LLM adapter for testing.

Returns deterministic responses without calling any external service.
"""

import json

from app.llm.base import AbstractLLMAdapter, LLMResponse

DEFAULT_RESPONSE = json.dumps(
    {
        "request_type": "access_request",
        "employee_name": "Jane Doe",
        "systems_requested": ["Salesforce", "Looker"],
        "manager_name": "Sarah Kim",
        "start_date": "2026-03-15",
        "urgency": "normal",
        "justification": "Revenue Ops onboarding",
        "recommended_action": "auto_approve",
        "notes": [],
    }
)


class MockLLMAdapter(AbstractLLMAdapter):
    """Mock adapter that returns pre-configured responses."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = responses or {}

    def generate_proposal(self, input_text: str, workflow_type: str) -> LLMResponse:
        """Return a custom response if configured, otherwise the default."""
        raw = self._responses.get(input_text, DEFAULT_RESPONSE)
        return LLMResponse(raw_response=raw, prompt_version="1.0")
