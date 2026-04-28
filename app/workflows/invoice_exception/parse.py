"""Proposal parser for the invoice_exception workflow."""

import json
import re

from pydantic import BaseModel, ValidationError

from app.workflows.invoice_exception.schema import Proposal

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


class ParseResult(BaseModel):
    """Result of parsing raw model output into a Proposal."""

    success: bool
    proposal: Proposal | None = None
    error: str | None = None


def _strip_fences(raw: str) -> str:
    match = _FENCE_RE.search(raw)
    return match.group(1).strip() if match else raw.strip()


def parse_proposal(raw_json: str) -> ParseResult:
    """Parse a raw JSON string into an invoice exception proposal."""
    try:
        data = json.loads(_strip_fences(raw_json))
    except (json.JSONDecodeError, TypeError) as exc:
        return ParseResult(success=False, error=f"JSON parse error: {exc}")

    if not isinstance(data, dict):
        return ParseResult(success=False, error="JSON must be an object")

    try:
        proposal = Proposal(**data)
    except ValidationError as exc:
        return ParseResult(success=False, error=str(exc))

    return ParseResult(success=True, proposal=proposal)
