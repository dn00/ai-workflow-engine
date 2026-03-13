"""Abstract LLM adapter interface and response model.

Provides the base interface for LLM adapters that generate proposals
from unstructured text input.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMResponse(BaseModel):
    """Structured response from an LLM adapter."""

    raw_response: str
    prompt_version: str
    model_id: str | None = None


class LLMAdapterError(Exception):
    """Raised when an LLM adapter encounters an error."""


class AbstractLLMAdapter(ABC):
    """Abstract base class for LLM adapters.

    Subclasses must implement generate_proposal() to produce structured
    proposal data from unstructured text.
    """

    @abstractmethod
    def generate_proposal(self, input_text: str, workflow_type: str) -> LLMResponse:
        """Generate a proposal from unstructured input text."""
        ...
