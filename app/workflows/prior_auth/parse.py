"""Parser for prior authorization LLM proposals."""

import json
import re

from pydantic import BaseModel, ValidationError

from app.workflows.prior_auth.schema import Proposal


class ParseResult(BaseModel):
    """Result of parsing an LLM response into a Proposal."""

    success: bool
    proposal: Proposal | None = None
    error: str | None = None


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def parse_proposal(raw_response: str) -> ParseResult:
    """Parse raw LLM JSON response into a Proposal. Never raises."""
    text = raw_response.strip()

    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return ParseResult(success=False, error=f"invalid_json: {exc}")

    if not isinstance(data, dict):
        return ParseResult(success=False, error="expected_json_object")

    try:
        proposal = Proposal(**data)
    except ValidationError as exc:
        return ParseResult(success=False, error=f"schema_error: {exc}")

    return ParseResult(success=True, proposal=proposal)
