"""Access-request-specific reason codes (spec §20).

These 6 codes are workflow-specific and live here rather than in
app.core.enums, per architecture §7/§27. Generic reason codes
remain in app.core.enums.ReasonCode.
"""

from enum import StrEnum


class AccessRequestReasonCode(StrEnum):
    """Access-request workflow reason codes (6 values)."""

    MISSING_MANAGER_NAME = "missing_manager_name"
    HIGH_URGENCY = "high_urgency"
    TOO_MANY_SYSTEMS = "too_many_systems"
    UNKNOWN_SYSTEM = "unknown_system"
    FORBIDDEN_SYSTEM = "forbidden_system"
    MANAGER_APPROVAL_UNVERIFIED = "manager_approval_unverified"
