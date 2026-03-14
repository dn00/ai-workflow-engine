# Architecture

## Core Thesis

**LLM proposes; deterministic system decides.**

The LLM extracts structured data from unstructured text. All committed decisions, state transitions, and side effects are controlled by deterministic code with explicit policy rules and audit trails.

## Four-Layer Architecture

```
Layer 4 — UX / API / Integrations
  FastAPI endpoints, Jinja2 templates, review actions, bundle export

Layer 3 — Runtime Layer
  LocalRunner, mode handling (LIVE / DRY_RUN / REPLAY)

Layer 2 — Deterministic Domain Engine
  Parser, validator, normalizer, policy engine, reducer, replay logic

Layer 1 — Persistence / System of Record
  SQLite (default), repositories, runs, events, reviews, receipts
```

**Dependency rule:** Each layer depends only on layers below it. Layer 2 (domain engine) contains pure functions with no I/O dependencies — it receives data and returns results.

### Layer 1 — Persistence

All persistence access goes through abstract repository interfaces (`app/db/repositories/`). The default implementation uses SQLite for near-zero setup. The repository pattern allows swapping to Postgres or another backend without changing domain or runtime code.

**Schema:** Three tables — `runs` (one row per workflow run), `events` (append-only event log), and `reviews` (review task / decision).

### Layer 2 — Deterministic Domain Engine

The domain engine lives in `app/workflows/access_request/` and `app/core/`. It handles:

- **Parsing** — extract structured fields from the LLM proposal receipt
- **Validation** — enforce hard rules (required fields, known systems, allowed values)
- **Normalization** — standardize system names, dates, employee names
- **Policy** — deterministic approve / review / reject decision based on request characteristics
- **Reduction** — fold events into a current-state projection

All domain logic is pure: no database calls, no network I/O. Data flows in, decisions flow out.

### Layer 3 — Runtime

The `LocalRunner` (`app/core/runners/`) orchestrates the full workflow lifecycle:

1. Accept input text and mode
2. Call the LLM adapter to generate a proposal receipt
3. Store the receipt, then pass it through parse → validate → normalize → policy
4. Emit events at each step to the append-only log
5. If policy approves: apply simulated effect and complete
6. If policy requires review: pause and wait for human decision
7. On review submission: resume from the review boundary
8. On replay: reconstruct from stored events/receipts without reapplying effects

### Layer 4 — API / UX

**API** (`app/api/`): Six REST endpoints for programmatic access — create runs, fetch run details, view event history, submit reviews, trigger replays, and export bundles.

**Web UI** (`app/web/`): Five Jinja2 template screens — intake form, run detail with event log, review form, and replay result viewer. Mounted at `/ui/`.

## Data Flow

```
Plain Text Input
      |
      v
LLM Proposal Receipt          [stored as-is before parsing]
      |
      v
Parse + Validate + Normalize   [deterministic, Layer 2]
      |
      v
Deterministic Policy Gate      [deterministic, Layer 2]
   /      |       \
  /       |        \
Reject   Review    Approve
          |          |
          v          v
    Reviewer Input   Simulated Effect
          \          /
           \        /
            v      v
       Append-Only Event History
                 |
                 v
          Final Projection / Replay Bundle
```

Every step emits one or more events to the append-only log, providing a complete audit trail.

## Extension Seams

The architecture is designed for extension without redesign:

| Seam | Interface | Current Implementation | Future |
|------|-----------|----------------------|--------|
| Runner | Abstract runner interface | LocalRunner | TemporalRunner (durable execution) |
| Persistence | Abstract repository interfaces | SQLite | Postgres |
| Effect Adapter | Abstract effect interface | Simulated approval | Real ticketing / IAM |
| Workflow Module | `app/workflows/{name}/` directory | `access_request/` | `invoice_intake/`, etc. |
| LLM Client | Abstract LLM adapter | Mock + CLI adapters | Multiple providers |
| Frontend | API endpoints (JSON) | Jinja2 templates | SPA, HTMX |

### Adding a New Workflow

To add a second workflow type, create a new module directory under `app/workflows/` with workflow-specific schema, validation, policy, and prompt files. The core kernel (`app/core/`) stays stable across workflow types.

## Directory Structure

```
app/
  api/                     # Layer 4: HTTP endpoints
    routes/
    schemas/
  web/                     # Layer 4: Web UI routes
  templates/               # Layer 4: Jinja2 templates
  core/                    # Layers 1-3: shared kernel
    events/                # event model, event creation
    receipts/              # receipt storage
    replay/                # replay logic
    projections/           # reducer / projection builder
    runners/               # runner interface + implementations
  workflows/
    access_request/        # workflow-specific module
  effects/                 # effect adapters
  db/                      # Layer 1: persistence
    repositories/
  llm/                     # LLM adapter interface + implementations
  services/                # application services
tests/
  unit/
  integration/
```
