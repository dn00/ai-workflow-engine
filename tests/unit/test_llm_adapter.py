"""Unit tests for the LLM adapter interface and mock implementation."""

import json

import pytest
from pydantic import ValidationError

from app.llm.base import AbstractLLMAdapter, LLMAdapterError, LLMResponse
from app.llm.mock_adapter import MockLLMAdapter


class TestAbstractAdapterNotInstantiable:
    # `test_abstract_adapter_not_instantiable`
    def test_abstract_adapter_not_instantiable(self):
        """AC-1: AbstractLLMAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractLLMAdapter()


class TestLLMResponseValid:
    # `test_llm_response_valid`
    def test_llm_response_valid(self):
        """AC-2: LLMResponse validates required fields; model_id defaults to None."""
        resp = LLMResponse(raw_response='{"foo": "bar"}', prompt_version="1.0")
        assert resp.raw_response == '{"foo": "bar"}'
        assert resp.prompt_version == "1.0"
        assert resp.model_id is None


class TestMockAdapterDefaultResponse:
    # `test_mock_adapter_default_response`
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
    # `test_mock_adapter_custom_response`
    def test_mock_adapter_custom_response(self):
        """AC-4: MockLLMAdapter returns custom responses when configured."""
        adapter = MockLLMAdapter(responses={"special": '{"custom": true}'})
        result = adapter.generate_proposal("special", "access_request")
        assert result.raw_response == '{"custom": true}'


class TestLLMAdapterErrorType:
    # `test_llm_adapter_error_type`
    def test_llm_adapter_error_type(self):
        """EC-1: LLMAdapterError is an Exception subclass with preserved message."""
        err = LLMAdapterError("something went wrong")
        assert isinstance(err, Exception)
        assert str(err) == "something went wrong"


class TestMockAdapterUnknownInputFallback:
    # `test_mock_adapter_unknown_input_fallback`
    def test_mock_adapter_unknown_input_fallback(self):
        """EC-2: MockLLMAdapter with unknown input falls back to default response."""
        adapter = MockLLMAdapter(responses={"x": "y"})
        result = adapter.generate_proposal("other", "access_request")
        data = json.loads(result.raw_response)
        assert "request_type" in data


class TestLLMResponseMissingRawResponse:
    # `test_llm_response_missing_raw_response`
    def test_llm_response_missing_raw_response(self):
        """ERR-1: LLMResponse rejects missing raw_response."""
        with pytest.raises(ValidationError):
            LLMResponse(prompt_version="1.0")
