"""Unit tests for the LLM adapter interface and mock implementation."""

import json

import pytest
from pydantic import ValidationError

from app.llm.base import AbstractLLMAdapter, LLMAdapterError, LLMResponse
from app.llm.mock_adapter import MockLLMAdapter


class TestAbstractAdapterNotInstantiable:
    # Task001 AC-1 `test_abstract_adapter_not_instantiable`
    """Task001 AC-1 test_abstract_adapter_not_instantiable"""

    def test_abstract_adapter_not_instantiable(self):
        """AC-1: AbstractLLMAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractLLMAdapter()


class TestLLMResponseValid:
    # Task001 AC-2 `test_llm_response_valid`
    """Task001 AC-2 test_llm_response_valid"""

    def test_llm_response_valid(self):
        """AC-2: LLMResponse validates required fields; model_id defaults to None."""
        resp = LLMResponse(raw_response='{"foo": "bar"}', prompt_version="1.0")
        assert resp.raw_response == '{"foo": "bar"}'
        assert resp.prompt_version == "1.0"
        assert resp.model_id is None


class TestMockAdapterDefaultResponse:
    # Task001 AC-3 `test_mock_adapter_default_response`
    """Task001 AC-3 test_mock_adapter_default_response"""

    def test_mock_adapter_default_response(self):
        """AC-3: MockLLMAdapter returns valid default JSON with all 9 proposal fields."""
        adapter = MockLLMAdapter()
        result = adapter.generate_proposal("any input", "access_request")
        assert isinstance(result, LLMResponse)
        data = json.loads(result.raw_response)
        expected_fields = {
            "request_type",
            "employee_name",
            "systems_requested",
            "manager_name",
            "start_date",
            "urgency",
            "justification",
            "recommended_action",
            "notes",
        }
        assert set(data.keys()) == expected_fields


class TestMockAdapterCustomResponse:
    # Task001 AC-4 `test_mock_adapter_custom_response`
    """Task001 AC-4 test_mock_adapter_custom_response"""

    def test_mock_adapter_custom_response(self):
        """AC-4: MockLLMAdapter returns custom responses when configured."""
        adapter = MockLLMAdapter(responses={"special": '{"custom": true}'})
        result = adapter.generate_proposal("special", "access_request")
        assert result.raw_response == '{"custom": true}'


class TestLLMAdapterErrorType:
    # Task001 EC-1 `test_llm_adapter_error_type`
    """Task001 EC-1 test_llm_adapter_error_type"""

    def test_llm_adapter_error_type(self):
        """EC-1: LLMAdapterError is an Exception subclass with preserved message."""
        err = LLMAdapterError("something went wrong")
        assert isinstance(err, Exception)
        assert str(err) == "something went wrong"


class TestMockAdapterUnknownInputFallback:
    # Task001 EC-2 `test_mock_adapter_unknown_input_fallback`
    """Task001 EC-2 test_mock_adapter_unknown_input_fallback"""

    def test_mock_adapter_unknown_input_fallback(self):
        """EC-2: MockLLMAdapter with unknown input falls back to default response."""
        adapter = MockLLMAdapter(responses={"x": "y"})
        result = adapter.generate_proposal("other", "access_request")
        data = json.loads(result.raw_response)
        assert "request_type" in data


class TestLLMResponseMissingRawResponse:
    # Task001 ERR-1 `test_llm_response_missing_raw_response`
    """Task001 ERR-1 test_llm_response_missing_raw_response"""

    def test_llm_response_missing_raw_response(self):
        """ERR-1: LLMResponse rejects missing raw_response."""
        with pytest.raises(ValidationError):
            LLMResponse(prompt_version="1.0")
