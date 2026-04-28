"""Models for deterministic workflow eval cases."""

from pydantic import BaseModel


class EvalExpected(BaseModel):
    """Expected outcome for one eval case."""

    status: str
    fields: dict = {}
    reason_codes_contains: list[str] = []
    reason_codes_absent: list[str] = []


class EvalCase(BaseModel):
    """Golden case for evaluating one workflow module."""

    name: str
    workflow_type: str
    input_text: str
    mock_response: str
    expected: EvalExpected
    slices: list[str] = []
