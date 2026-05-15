"""Clinical code validation and classification for prior authorization policy routing."""

import re

VALID_ICD10_PATTERN = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")
VALID_CPT_PATTERN = re.compile(r"^\d{5}$")
VALID_NPI_PATTERN = re.compile(r"^\d{10}$")

HIGH_COST_PROCEDURES: frozenset[str] = frozenset(
    {
        "27447",  # total knee arthroplasty
        "27130",  # total hip arthroplasty
        "22630",  # lumbar spinal fusion
        "33533",  # CABG single arterial graft
        "27487",  # revision knee arthroplasty
        "22612",  # posterior lumbar interbody fusion
    }
)

ALWAYS_REVIEW_PROCEDURES: frozenset[str] = frozenset(
    {
        "20930",  # allograft bone grafting
        "22857",  # artificial disc replacement
        "27580",  # knee arthrodesis
        "64999",  # unlisted nervous system procedure
        "17999",  # unlisted dermatological procedure
    }
)

AUTO_APPROVE_PROCEDURES: frozenset[str] = frozenset(
    {
        "73721",  # MRI knee without contrast
        "73221",  # MRI upper extremity joint without contrast
        "73718",  # MRI lower extremity without contrast
        "70553",  # MRI brain with and without contrast
        "71260",  # CT chest with contrast
        "71250",  # CT chest without contrast
        "72148",  # MRI lumbar spine without contrast
        "73630",  # X-ray foot
        "73610",  # X-ray ankle
        "73030",  # X-ray shoulder
        "97110",  # therapeutic exercises
        "97140",  # manual therapy
        "97530",  # therapeutic activities
    }
)

KNOWN_PAYERS: frozenset[str] = frozenset(
    {
        "aetna",
        "cigna",
        "unitedhealthcare",
        "uhc",
        "united healthcare",
        "anthem",
        "blue cross",
        "blue cross blue shield",
        "bcbs",
        "humana",
        "kaiser",
        "kaiser permanente",
        "medicare",
        "medicaid",
        "tricare",
        "molina",
        "centene",
        "wellcare",
    }
)

RESTRICTED_PAYERS: frozenset[str] = frozenset(
    {
        "medicare",
        "medicaid",
        "tricare",
    }
)


def classify_procedure(cpt_code: str) -> str:
    """Classify a CPT code by risk tier.

    Returns: 'auto_approve', 'high_cost', 'always_review', or 'standard'.
    """
    code = cpt_code.strip()
    if code in ALWAYS_REVIEW_PROCEDURES:
        return "always_review"
    if code in HIGH_COST_PROCEDURES:
        return "high_cost"
    if code in AUTO_APPROVE_PROCEDURES:
        return "auto_approve"
    return "standard"


def classify_payer(name: str) -> str:
    """Classify a payer as known, restricted, or unknown."""
    normalized = name.strip().lower()
    if normalized in RESTRICTED_PAYERS:
        return "restricted"
    if normalized in KNOWN_PAYERS:
        return "known"
    return "unknown"


def is_valid_icd10(code: str) -> bool:
    """Check if a string matches ICD-10-CM format."""
    return bool(VALID_ICD10_PATTERN.match(code.strip().upper()))


def is_valid_cpt(code: str) -> bool:
    """Check if a string matches CPT code format (5 digits)."""
    return bool(VALID_CPT_PATTERN.match(code.strip()))


def is_valid_npi(npi: str) -> bool:
    """Check if a string matches NPI format (10 digits)."""
    return bool(VALID_NPI_PATTERN.match(npi.strip()))
