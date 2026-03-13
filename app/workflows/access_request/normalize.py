"""Field normalizer for the access_request workflow (architecture §4).

Transforms raw Proposal fields into clean, canonical NormalizedFields.
This function never raises — validation happens downstream in validate.py.
"""

import re

from app.workflows.access_request.schema import NormalizedFields, Proposal


def _clean_name(value: str | None) -> str | None:
    """Strip and normalize internal whitespace. None → None."""
    if value is None:
        return None
    return re.sub(r"\s+", " ", value.strip())


def normalize_proposal(proposal: Proposal) -> NormalizedFields:
    """Normalize proposal fields into canonical form.

    Transformations:
    - employee_name: strip whitespace, normalize internal spacing. None → ""
    - systems_requested: lowercase each, strip whitespace. None → []
    - manager_name: strip whitespace, normalize spacing. None → None (preserved)
    """
    employee_name = _clean_name(proposal.employee_name) or ""

    systems = proposal.systems_requested or []
    systems_requested = [s.strip().lower() for s in systems]

    manager_name = _clean_name(proposal.manager_name)

    return NormalizedFields(
        employee_name=employee_name,
        systems_requested=systems_requested,
        manager_name=manager_name,
    )
