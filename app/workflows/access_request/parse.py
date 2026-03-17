"""Proposal parser for the access_request workflow (spec §17).

Parses raw JSON strings (LLM output) into validated Proposal models.
Does NOT store receipts — that's the runner's responsibility (INV-1.2).
"""

import json
import re

from pydantic import BaseModel, ValidationError

from app.workflows.access_request.schema import Proposal

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


class ParseResult(BaseModel):
    """Result of parsing a raw JSON string into a Proposal."""

    success: bool
    proposal: Proposal | None = None
    error: str | None = None


def _strip_fences(raw: str) -> str:
    """Strip markdown code fences if present, returning the inner content."""
    m = _FENCE_RE.search(raw)
    return m.group(1).strip() if m else raw.strip()


def parse_proposal(raw_json: str) -> ParseResult:
    """Parse a raw JSON string into a Proposal model.

    Steps:
    1. Strip markdown code fences if present
    2. Attempt JSON decode (json.loads)
    3. Attempt Pydantic validation (Proposal(**data))
    4. Return ParseResult with success/failure
    """
    try:
        data = json.loads(_strip_fences(raw_json))
    except (json.JSONDecodeError, TypeError) as e:
        return ParseResult(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return ParseResult(success=False, error="JSON must be an object")

    try:
        proposal = Proposal(**data)
    except ValidationError as e:
        return ParseResult(success=False, error=str(e))

    return ParseResult(success=True, proposal=proposal)
