"""System allowlist for the access_request workflow (spec §19).

Classifies system names into low_risk, forbidden, known, or unknown.
Used by the validator (feature 006) and policy engine (feature 007).
"""

LOW_RISK_SYSTEMS: frozenset[str] = frozenset({
    "salesforce", "looker", "jira", "confluence",
    "slack", "google_workspace", "github",
})

FORBIDDEN_SYSTEMS: frozenset[str] = frozenset({
    "admin_console", "root_access", "production_db",
})

KNOWN_SYSTEMS: frozenset[str] = LOW_RISK_SYSTEMS | frozenset({
    "aws", "azure", "gcp", "datadog",
})


def classify_system(name: str) -> str:
    """Classify a normalized system name.

    Returns: 'low_risk', 'forbidden', 'known', or 'unknown'.
    Input is lowercased and stripped before classification.
    """
    normalized = name.strip().lower()
    if normalized in FORBIDDEN_SYSTEMS:
        return "forbidden"
    if normalized in LOW_RISK_SYSTEMS:
        return "low_risk"
    if normalized in KNOWN_SYSTEMS:
        return "known"
    return "unknown"
