"""Vendor classification for invoice exception policy routing."""

KNOWN_VENDORS: frozenset[str] = frozenset(
    {
        "acme",
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
    }
)

FLAGGED_VENDORS: frozenset[str] = frozenset(
    {
        "offshore consulting ltd",
        "untraceable services",
    }
)


def classify_vendor(name: str) -> str:
    """Classify a vendor as known, flagged, or unknown."""
    normalized = name.strip().lower()
    if normalized in FLAGGED_VENDORS:
        return "flagged"
    if normalized in KNOWN_VENDORS:
        return "known"
    return "unknown"
