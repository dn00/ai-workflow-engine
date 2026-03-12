"""Proposal schema for the access_request workflow (spec §17).

All fields are optional because the LLM output is untrusted input
(INV-1.2). Validation rules (feature 006) enforce which fields
are required for the run to proceed.
"""

from pydantic import BaseModel


class Proposal(BaseModel):
    """LLM-generated proposal for an access request (9 frozen fields)."""

    request_type: str | None = None
    employee_name: str | None = None
    systems_requested: list[str] | None = None
    manager_name: str | None = None
    start_date: str | None = None
    urgency: str | None = None
    justification: str | None = None
    recommended_action: str | None = None
    notes: list[str] | None = None
