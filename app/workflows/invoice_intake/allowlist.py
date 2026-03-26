"""Vendor allowlist for the invoice_intake workflow.

Classifies vendor names into known, flagged, or unknown.
"""

KNOWN_VENDORS: frozenset[str] = frozenset({
    "acme corp",
    "globex",
    "initech",
    "contoso",
    "northwind traders",
    "aws",
    "google cloud",
    "microsoft",
    "datadog",
    "snowflake",
})

FLAGGED_VENDORS: frozenset[str] = frozenset({
    "offshore consulting ltd",
    "untraceable services",
})


def classify_vendor(name: str) -> str:
    """Classify a vendor name. Returns 'known', 'flagged', or 'unknown'."""
    normalized = name.strip().lower()
    if normalized in FLAGGED_VENDORS:
        return "flagged"
    if normalized in KNOWN_VENDORS:
        return "known"
    return "unknown"
