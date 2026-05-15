# Prior Authorization Workflow — Implementation Plan

## Goal

Add a `prior_auth` workflow module that demonstrates AI-driven prior authorization using FHIR R4 resources. An unstructured clinical note or referral enters the pipeline, the LLM extracts structured clinical facts, deterministic code validates and builds FHIR resources, and the policy engine routes the request through approval, clinical review, or rejection.

This follows the project thesis: **LLMs propose, deterministic code decides.**

## Why Prior Auth

Prior authorization is the highest-value intersection of AI + FHIR + healthcare integration:

- CMS-0057 mandates FHIR-based prior auth by 2027 — every payer and health system is hiring for this
- The workflow maps 1:1 to the existing engine: LLM extraction → validation → policy gate → human review → effect
- Demonstrates real FHIR R4 resource handling, clinical code systems (ICD-10, CPT), and safety-critical AI decision support

---

## Phase 1: Core Workflow Module

### 1.1 Schema (`app/workflows/prior_auth/schema.py`)

The LLM extracts a `Proposal` from unstructured clinical text. All fields optional (untrusted LLM output).

```python
class Diagnosis(BaseModel):
    code: str | None = None        # ICD-10 code (e.g., "M17.11")
    display: str | None = None     # human-readable name
    rank: str | None = None        # "primary" or "secondary"

class Procedure(BaseModel):
    code: str | None = None        # CPT code (e.g., "27447")
    display: str | None = None
    quantity: int | None = None

class Proposal(BaseModel):
    request_type: str | None = None              # always "prior_auth"
    patient_id: str | None = None                # patient reference
    provider_name: str | None = None             # requesting provider
    provider_npi: str | None = None              # NPI number
    payer_name: str | None = None                # insurance carrier
    payer_id: str | None = None                  # payer identifier
    diagnoses: list[Diagnosis] | None = None     # ICD-10 codes
    procedures: list[Procedure] | None = None    # CPT codes requested
    service_date: str | None = None              # requested service date
    urgency: str | None = None                   # "routine", "urgent", "emergent"
    clinical_justification: str | None = None    # free-text medical necessity
    prior_treatments: list[str] | None = None    # conservative treatments tried
    notes: list[str] | None = None               # LLM-flagged ambiguities
```

`NormalizedFields` adds computed fields:

```python
class NormalizedFields(BaseModel):
    patient_id: str
    provider_name: str
    provider_npi: str
    payer_name: str
    payer_id: str
    diagnoses: list[Diagnosis]
    procedures: list[Procedure]
    service_date: str
    urgency: str                            # normalized to lowercase
    clinical_justification: str
    prior_treatments: list[str]
    primary_diagnosis: Diagnosis | None     # extracted from diagnoses list
    all_codes_valid: bool                   # ICD-10/CPT format check
    has_medical_necessity: bool             # justification + prior treatments present
    review_packet: ReviewPacket             # human-readable summary
```

`ReviewPacket` provides a human-readable summary for the review UI:

```python
class ReviewPacket(BaseModel):
    summary: str                  # one-line clinical summary
    findings: list[str]           # policy triggers and clinical notes
    fhir_claim_preview: dict      # serialized FHIR Claim resource for review
```

### 1.2 Allowlist (`app/workflows/prior_auth/allowlist.py`)

Classification functions for clinical code validation and payer/procedure risk tiers.

```python
# Code format validators (regex-based, not exhaustive lookup tables)
VALID_ICD10_PATTERN = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")
VALID_CPT_PATTERN = re.compile(r"^\d{5}$")
VALID_NPI_PATTERN = re.compile(r"^\d{10}$")

# Procedure risk tiers
HIGH_COST_PROCEDURES: frozenset[str]     # e.g., "27447" (knee replacement), "27130" (hip replacement)
ALWAYS_REVIEW_PROCEDURES: frozenset[str] # e.g., experimental, cosmetic-adjacent
AUTO_APPROVE_PROCEDURES: frozenset[str]  # e.g., routine imaging, standard labs

# Payer classification
KNOWN_PAYERS: frozenset[str]             # e.g., "aetna", "cigna", "unitedhealthcare", "medicare"
RESTRICTED_PAYERS: frozenset[str]        # payers with strict auth requirements

def classify_procedure(cpt_code: str) -> str:
    """Returns: 'auto_approve', 'standard', 'high_cost', 'always_review', or 'unknown'."""

def classify_payer(name: str) -> str:
    """Returns: 'known', 'restricted', or 'unknown'."""

def is_valid_icd10(code: str) -> bool:
def is_valid_cpt(code: str) -> bool:
def is_valid_npi(npi: str) -> bool:
```

### 1.3 Parse (`app/workflows/prior_auth/parse.py`)

Standard pattern: strip markdown fences, `json.loads`, construct `Proposal`. Returns `ParseResult`. Never raises.

### 1.4 Normalize (`app/workflows/prior_auth/normalize.py`)

- Clean whitespace on all string fields
- Normalize urgency to lowercase
- Default empty lists for `None` diagnoses/procedures/prior_treatments
- Extract `primary_diagnosis` from diagnoses list (first with `rank == "primary"`, or first in list)
- Validate code formats → set `all_codes_valid` bool
- Determine `has_medical_necessity` (justification present AND prior_treatments non-empty)
- Build `ReviewPacket` with human-readable summary
- Build FHIR Claim preview for `review_packet.fhir_claim_preview`

### 1.5 Validate (`app/workflows/prior_auth/validate.py`)

Hard validation — data integrity, not policy:

| Check | Error Code |
|-------|-----------|
| `request_type != "prior_auth"` | `unsupported_request_type` |
| Missing patient_id | `missing_patient_id` |
| Missing provider_name | `missing_provider_name` |
| Invalid NPI format | `invalid_npi_format` |
| Missing payer | `missing_payer` |
| No diagnoses | `missing_diagnoses` |
| No procedures | `missing_procedures` |
| Invalid ICD-10 format | `invalid_icd10_code` |
| Invalid CPT format | `invalid_cpt_code` |
| Missing service_date | `missing_service_date` |
| Malformed service_date | `malformed_date` |
| Service date in past | `service_date_in_past` |

Accumulates all errors, returns `ValidationResult(is_valid=bool, errors=list)`.

### 1.6 Policy (`app/workflows/prior_auth/policy.py`)

Deterministic clinical authorization rules:

```
IF validation failed → rejected (with error codes)

IF any procedure in ALWAYS_REVIEW → review_required ["always_review_procedure"]
IF payer is restricted → review_required ["restricted_payer"]
IF any procedure is high_cost:
    IF no medical necessity → review_required ["high_cost_no_necessity"]
    IF has medical necessity → review_required ["high_cost_clinical_review"]
IF urgency == "emergent" → approved ["emergent_bypass"]
IF all procedures auto_approve AND known payer AND valid codes → approved
IF unknown procedure codes → review_required ["unknown_procedure"]
IF unknown payer → review_required ["unknown_payer"]
IF missing medical necessity on non-routine → review_required ["missing_medical_necessity"]

Default: review_required ["standard_clinical_review"]
```

Conservative by design — prior auth should default to human review. Auto-approve only for routine + known + valid combinations.

### 1.7 LLM Integration (`app/workflows/prior_auth/prompt.py`)

This is the AI core — turning messy clinical notes into structured proposals. The runner already handles wiring: `CliLLMAdapter` reads `wf.SYSTEM_PROMPT`, calls `wf.build_user_prompt(input_text)`, sends both to Claude, and returns raw JSON for parsing. The workflow module controls the extraction quality through prompt engineering.

**Why this is hard (and impressive):** Real clinical notes are messy. Providers write "pt c/o R knee pain x 6 wks, failed PT/NSAIDs, MRI requested r/o meniscal tear" — abbreviations, shorthand, implicit codes. The LLM must map this to structured ICD-10/CPT codes, identify the medical necessity argument, and surface what's missing. This is the gap between a toy demo and a credible integration engineering portfolio piece.

**System prompt design:**

```python
PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """You are a clinical prior authorization extraction system.

You receive a clinical note, referral, or prior authorization request. Your job
is to extract structured clinical facts for submission to a payer. You do NOT
make authorization decisions — you extract what is present and flag what is
missing.

Return ONLY a JSON object with exactly these fields:

- request_type: always "prior_auth"
- patient_id: patient identifier or MRN if present
- provider_name: requesting/referring provider name
- provider_npi: 10-digit NPI if present, null if not stated
- payer_name: insurance carrier / health plan name
- payer_id: payer identifier if present, null if not stated
- diagnoses: array of objects, each with:
    - code: ICD-10-CM code (e.g., "M17.11"). Infer from clinical description
      if not explicitly stated. Use the most specific code supported by the
      documentation.
    - display: human-readable diagnosis name
    - rank: "primary" or "secondary"
- procedures: array of objects, each with:
    - code: CPT code (e.g., "27447"). Infer from procedure description if not
      explicitly coded.
    - display: human-readable procedure name
    - quantity: number of units, default 1
- service_date: requested date of service (ISO 8601), null if not stated
- urgency: "routine", "urgent", or "emergent" — infer from clinical context
- clinical_justification: the medical necessity argument. Combine the provider's
  stated reasoning. Include relevant clinical findings, failed treatments, and
  why the requested service is needed. This is the most important field for
  authorization decisions.
- prior_treatments: array of conservative/prior treatments the patient has
  already tried (e.g., ["physical therapy x 6 weeks", "naproxen 500mg BID",
  "corticosteroid injection"]). Extract from the clinical narrative. Empty array
  if none documented.
- notes: array of ambiguities, missing information, or assumptions you made
  during extraction. Examples:
    - "NPI not stated in referral, field left null"
    - "ICD-10 code inferred from clinical description, not explicitly documented"
    - "No payer information found — extracted from letterhead"

Clinical abbreviations you should recognize:
- pt = patient, c/o = complaining of, hx = history, dx = diagnosis
- R/L = right/left, b/l = bilateral, w/ = with, w/o = without
- r/o = rule out, s/p = status post, f/u = follow up
- PT = physical therapy, NSAIDs = non-steroidal anti-inflammatory drugs
- MRI/CT/XR = imaging modalities, ROM = range of motion
- TKA/THA = total knee/hip arthroplasty, ACL = anterior cruciate ligament

When a clinical description implies a diagnosis or procedure but no code is
given, infer the most likely ICD-10 or CPT code. Document this inference in
the notes array.

Do not decide authorization. Extract and structure only.
Return ONLY valid JSON. No markdown fences, no explanation, no extra text."""
```

**User prompt builder:**

```python
def build_user_prompt(input_text: str, retrieved_context: str | None = None) -> str:
    context = retrieved_context or "No payer policy context available."
    return f"""Extract prior authorization facts from the following clinical
documentation.

Payer policy context (use to identify relevant medical necessity criteria):
---
{context}
---

Clinical documentation:
---
{input_text}
---

Return the JSON object specified by the system instructions."""
```

**Mock LLM responses** (`app/workflows/prior_auth/mock_responses.py`):

Pre-built mock responses for each demo scenario so the workflow runs end-to-end without a live LLM. Used by `MockLLMAdapter` in tests and local dev:

```python
MOCK_RESPONSES = {
    "routine_imaging": {
        "request_type": "prior_auth",
        "patient_id": "PAT-001",
        "provider_name": "Dr. Sarah Chen",
        "provider_npi": "1234567890",
        "payer_name": "Aetna",
        "payer_id": "AETNA-001",
        "diagnoses": [
            {"code": "M17.11", "display": "Primary osteoarthritis, right knee", "rank": "primary"}
        ],
        "procedures": [
            {"code": "73721", "display": "MRI knee without contrast", "quantity": 1}
        ],
        "service_date": "2026-06-15",
        "urgency": "routine",
        "clinical_justification": "Persistent right knee pain x 6 weeks, unresponsive to physical therapy and NSAIDs. ROM limited to 90 degrees flexion. MRI indicated to evaluate for meniscal tear or ligament injury.",
        "prior_treatments": ["physical therapy x 6 weeks", "naproxen 500mg BID x 4 weeks"],
        "notes": []
    },
    "knee_replacement": { ... },
    "missing_justification": { ... },
    "emergent_cardiac": { ... },
    "invalid_codes": { ... },
}
```

**What the LLM integration demonstrates to interviewers:**

1. **Unstructured → structured extraction** from real clinical language, not clean form data
2. **Clinical code inference** — LLM maps "knee pain" → `M17.11`, "MRI knee" → `73721`
3. **Medical necessity assembly** — LLM synthesizes justification from scattered clinical notes
4. **Uncertainty surfacing** — `notes` field flags inferences and missing data instead of hallucinating
5. **Separation of concerns** — LLM extracts, deterministic code validates and decides (project thesis)
6. **Prompt versioning** — `PROMPT_VERSION` ties extraction quality to a specific prompt, enabling eval tracking

### 1.8 Registration

Add to `app/workflows/__init__.py`:

```python
from app.workflows import prior_auth
register_workflow("prior_auth", prior_auth)
```

---

## Phase 2: FHIR R4 Resource Generation

### 2.1 FHIR Builder (`app/workflows/prior_auth/fhir_builder.py`)

Builds FHIR R4 resources from `NormalizedFields`. Uses `fhir.resources` (Pydantic-based FHIR R4 models — matches our stack).

**Resources generated:**

| FHIR Resource | Purpose | Built From |
|--------------|---------|-----------|
| `Claim` (type: preauthorization) | The prior auth request itself | Full NormalizedFields |
| `Patient` (reference) | Patient stub | patient_id |
| `Practitioner` (reference) | Requesting provider | provider_name, provider_npi |
| `Organization` (reference) | Payer | payer_name, payer_id |
| `ClaimResponse` | Authorization decision | Policy decision + reason codes |

```python
def build_prior_auth_claim(normalized: NormalizedFields) -> Claim:
    """Build a FHIR R4 Claim with use='preauthorization'."""
    # - Claim.use = "preauthorization"
    # - Claim.type = CodeableConcept for "professional"
    # - Claim.diagnosis[] from normalized.diagnoses (ICD-10 coding)
    # - Claim.procedure[] from normalized.procedures (CPT coding)
    # - Claim.item[] with service date and quantity
    # - Claim.provider reference to Practitioner
    # - Claim.insurer reference to Organization
    # - Claim.patient reference to Patient

def build_claim_response(
    claim: Claim,
    decision: ValidatedDecision,
) -> ClaimResponse:
    """Build FHIR R4 ClaimResponse from policy decision."""
    # - outcome: "complete" (approved), "queued" (review_required), "error" (rejected)
    # - disposition: human-readable decision summary
    # - processNote[]: reason codes as adjudication notes

def bundle_resources(claim: Claim, response: ClaimResponse) -> Bundle:
    """Wrap claim + response in a FHIR Bundle (type: collection)."""
```

### 2.2 Dependency

Add `fhir.resources` to `pyproject.toml`:

```toml
[project.optional-dependencies]
fhir = ["fhir.resources>=7.0.0"]
```

Keep it optional so existing workflows aren't affected. The prior_auth module imports it directly.

---

## Phase 3: Effect Adapter

### 3.1 Simulated FHIR Effect (`app/effects/fhir_effect.py`)

A simulated effect adapter that "submits" the FHIR Claim to a payer endpoint.

```python
class SimulatedFhirEffectAdapter(AbstractEffectAdapter):
    def execute(self, run_id: str, idempotency_key: str) -> dict:
        """Simulate submitting a prior auth claim to a payer FHIR endpoint."""
        return {
            "effect_type": "fhir_prior_auth_submission",
            "simulated": True,
            "endpoint": "https://payer.example.com/fhir/r4/Claim/$submit",
            "status": "accepted",
            "auth_number": f"AUTH-{run_id[:8].upper()}",
            "timestamp": datetime.utcnow().isoformat(),
        }
```

---

## Phase 4: Sample Data & Demo

### 4.1 Sample Clinical Notes (`data/prior_auth/`)

Create 4-5 realistic clinical referral notes covering key scenarios:

| File | Scenario | Expected Outcome |
|------|----------|-----------------|
| `routine_imaging.txt` | MRI knee, known payer, valid codes, conservative treatment documented | approved |
| `knee_replacement.txt` | Total knee arthroplasty, high-cost, medical necessity documented | review_required (high_cost_clinical_review) |
| `missing_justification.txt` | Surgery request, no prior treatments listed | review_required (missing_medical_necessity) |
| `emergent_cardiac.txt` | Emergency cardiac catheterization, urgency=emergent | approved (emergent_bypass) |
| `invalid_codes.txt` | Malformed ICD-10 and CPT codes | rejected (validation errors) |

### 4.2 Golden Test Fixtures (`tests/golden/fixtures/`)

Add prior_auth eval cases following existing fixture format:

```json
{
  "name": "prior_auth_routine_approved",
  "input": {
    "request_type": "prior_auth",
    "patient_id": "PAT-001",
    "provider_name": "Dr. Sarah Chen",
    "provider_npi": "1234567890",
    "payer_name": "Aetna",
    "payer_id": "AETNA-001",
    "diagnoses": [{"code": "M17.11", "display": "Primary osteoarthritis, right knee", "rank": "primary"}],
    "procedures": [{"code": "73721", "display": "MRI knee without contrast", "quantity": 1}],
    "service_date": "2026-06-15",
    "urgency": "routine",
    "clinical_justification": "Persistent knee pain unresponsive to 6 weeks of physical therapy and NSAIDs.",
    "prior_treatments": ["physical therapy", "naproxen 500mg BID"]
  },
  "expected_decision": {
    "status": "approved",
    "reason_codes": [],
    "allowed_actions": ["create_simulated_approval_task"]
  }
}
```

---

## Phase 5: Tests

### 5.1 Unit Tests (`tests/unit/test_prior_auth_*.py`)

Follow existing patterns (one file per component or grouped):

| Test File | Coverage |
|-----------|----------|
| `test_prior_auth_parse.py` | Valid JSON, malformed JSON, missing fields, markdown fences |
| `test_prior_auth_normalize.py` | Whitespace cleanup, code validation, primary diagnosis extraction, medical necessity flag, default handling |
| `test_prior_auth_validate.py` | Each error code in isolation, accumulation of multiple errors, edge cases (past dates, malformed codes) |
| `test_prior_auth_policy.py` | Each policy branch: auto-approve routine, review high-cost, review missing necessity, emergent bypass, restricted payer, rejection on validation failure |
| `test_prior_auth_allowlist.py` | Code format validators, procedure classification, payer classification |
| `test_prior_auth_fhir.py` | FHIR Claim construction, ClaimResponse mapping, Bundle assembly, resource serialization round-trip |

### 5.2 Integration Tests (`tests/integration/test_prior_auth_e2e.py`)

Full pipeline through LocalRunner with mock LLM:

- Submit clinical note → auto-approved → verify event sequence + FHIR resources in projection
- Submit → review_required → submit review → approved → verify
- Submit → rejected (validation) → verify terminal state
- Replay a completed prior auth run → verify projection matches

### 5.3 Golden Evals

Add prior_auth cases to eval harness. Target: 5+ deterministic eval cases passing.

---

## Phase 6: LLM Extraction Eval Suite

The deterministic golden evals (Phase 5) test parse → validate → policy with pre-built JSON. This phase tests the full AI loop: clinical note → LLM extraction → structured output quality.

### 6.1 Extraction Eval Cases (`evals/prior_auth/`)

Each case pairs a raw clinical note with expected extraction fields:

```python
{
    "name": "abbreviation_heavy_referral",
    "input_text": "Pt is 62yo F c/o R knee pain x 6 wks. Hx of OA. Failed PT x 6 wks, NSAIDs. ROM 90deg flexion. Req MRI R knee r/o meniscal tear. Dx: M17.11. Dr. Chen, NPI 1234567890. Aetna.",
    "expected_fields": {
        "diagnoses[0].code": "M17.11",
        "procedures[0].code": "73721",
        "urgency": "routine",
        "prior_treatments": ["physical therapy", "NSAIDs"],  # partial match OK
        "provider_npi": "1234567890",
    },
    "extraction_checks": [
        "clinical_justification is not empty",
        "notes mentions MRI code was inferred if not in source",
    ]
}
```

**Eval dimensions:**

| Dimension | What It Tests | Pass Criteria |
|-----------|--------------|---------------|
| **Code accuracy** | ICD-10/CPT extraction/inference | Exact match on explicitly stated codes, reasonable inference on implied |
| **Completeness** | All fields populated when source data exists | No null fields when source contains the information |
| **Abbreviation handling** | Clinical shorthand decoded correctly | "PT" → physical therapy, "c/o" → complaining of |
| **Uncertainty honesty** | Notes flag inferences vs stated facts | Inferred codes appear in notes array |
| **Medical necessity** | Justification assembled from scattered notes | clinical_justification non-empty, references findings and failed treatments |
| **Robustness** | Handles varied note formats | Structured referral, free-text note, bullet-point summary all extract correctly |

### 6.2 Running LLM Evals

```bash
make eval-prior-auth   # runs extraction evals against live LLM
```

Uses `CliLLMAdapter` with real Claude calls. Eval harness compares extracted fields against expected values, reports per-field accuracy, and flags regressions when prompt version changes.

This is where prompt iteration happens: change `SYSTEM_PROMPT` → bump `PROMPT_VERSION` → run evals → compare. The eval suite is the feedback loop that makes the AI actually work.

---

## Phase 7: Retrieval (Optional Enhancement)

### 6.1 Payer Policy Documents (`app/workflows/prior_auth/retrieval.py`)

If time allows, add payer-specific medical policy documents to the retrieval layer:

```python
def build_retrieval_query(input_text: str) -> str:
    """Broad query for initial clinical context retrieval."""

def build_policy_query(proposal: Proposal, normalized: NormalizedFields) -> str:
    """Focused query using extracted diagnosis/procedure codes and payer."""
    return f"{normalized.payer_name} prior auth policy {normalized.primary_diagnosis.code} {normalized.procedures[0].code}"
```

Load sample payer policy PDFs into `docs/policies/` (e.g., "Aetna knee replacement medical necessity criteria"). The LLM can then cite evidence IDs in its extraction, and the policy engine can factor in whether evidence was cited.

---

## Implementation Order

```
 1. schema.py + allowlist.py        (data model, no deps)
 2. parse.py + normalize.py         (pure transforms)
 3. validate.py                     (hard rules)
 4. policy.py                       (decision routing)
 5. prompt.py + mock_responses.py   (LLM extraction — the AI core)
 6. __init__.py + registration      (wire into engine)
 7. Unit tests for 1-6              (verify each component)
 8. Integration test                (full pipeline with mock LLM)
 9. Sample clinical notes           (realistic demo inputs)
10. Golden eval fixtures            (deterministic policy evals)
11. LLM extraction evals            (live LLM accuracy testing)
12. fhir_builder.py                 (FHIR R4 resource generation)
13. fhir effect adapter             (simulated payer submission)
14. Retrieval (stretch)             (payer policy RAG)
```

Steps 1-8 produce a working workflow with no new dependencies.
Steps 9-11 make it demo-ready and test the AI extraction quality.
Steps 12-13 add FHIR resource layer.
Step 14 is a stretch goal.

---

## Files Created/Modified

**New files (14-16):**
```
app/workflows/prior_auth/__init__.py
app/workflows/prior_auth/schema.py
app/workflows/prior_auth/allowlist.py
app/workflows/prior_auth/parse.py
app/workflows/prior_auth/normalize.py
app/workflows/prior_auth/validate.py
app/workflows/prior_auth/policy.py
app/workflows/prior_auth/prompt.py
app/workflows/prior_auth/fhir_builder.py
app/workflows/prior_auth/retrieval.py          # optional
app/effects/fhir_effect.py
data/prior_auth/*.txt                          # sample clinical notes
tests/unit/test_prior_auth_*.py
tests/golden/fixtures/prior_auth_*.json
```

**Modified files (2-3):**
```
app/workflows/__init__.py                      # register prior_auth
pyproject.toml                                 # add fhir.resources dep
README.md                                      # add prior_auth to docs
```
