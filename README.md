# ai-workflow-engine

**Deterministic AI Workflow Automation**

A production-shaped AI workflow automation system that converts unstructured access requests into safe, replayable, auditable actions. The core thesis: **LLMs propose, deterministic code decides** — LLM output is treated as untrusted input, gated by validation, policy rules, and human review before any side effects execute.

## Quick Start

**Prerequisites:** Python >= 3.11, `uv`, [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (optional, for real LLM calls)

```bash
# Install dependencies
make install

# Start the demo server (uses Claude CLI for LLM extraction)
make demo

# Or run with mock LLM (no Claude CLI needed)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The server starts at `http://127.0.0.1:8000`. Open `http://127.0.0.1:8000/ui/intake` for the web UI, or `http://127.0.0.1:8000/docs` for the interactive API docs.

## How It Works

A plain-text access request flows through a deterministic pipeline:

```
User submits natural language request
    |
    v
LLM extracts structured proposal (stored as receipt before parsing)
    |
    v
Validate: required fields, system allowlist, forbidden systems
    |
    +--> validation failure --> terminal (no effects)
    |
    v
Policy gate: approve / review_required / reject
    |
    +--> rejected --> terminal (no effects)
    |
    +--> review_required --> pause for human --> approve or reject
    |
    +--> approved --> execute simulated effect --> completed
```

Every step emits an event to an append-only log. The current state is derived by folding events through a reducer — enabling deterministic replay and audit.

## Demo Scenarios

| Scenario | Input | Outcome |
|----------|-------|---------|
| **Auto-approve** | Single low-risk system (e.g. Confluence), manager present | Policy approves, effect simulated |
| **Human review** | High urgency or known system (e.g. AWS) | Pauses at `review_required`, resumes after human decision |
| **Rejection** | Forbidden system (e.g. production_db) | Blocked at validation, no effects |
| **Replay** | Any completed run | Reconstructs from events, verifies projection matches |

See [docs/demo-script.md](docs/demo-script.md) for step-by-step API and UI walkthroughs.

## Architecture

Four layers with strict downward dependencies:

| Layer | Responsibility | Key modules |
|-------|---------------|-------------|
| **4 — API / UX** | HTTP interface | FastAPI REST (6 endpoints), Jinja2 web UI |
| **3 — Runtime** | Orchestration | LocalRunner, LLM + effect adapters |
| **2 — Domain** | Pure logic | Parser, validator, normalizer, policy engine, reducer |
| **1 — Persistence** | Storage | SQLite, abstract repositories, append-only events |

Layer 2 is pure — no I/O, no side effects. Layer 3 orchestrates I/O around Layer 2 calls. Layer 4 is a thin shell. All interfaces are abstract, so any layer can be swapped (e.g. Postgres, real IAM effects, Temporal runner).

See [docs/architecture.md](docs/architecture.md) for the full design including state machine, event model, data flow, and extension seams.

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/runs/` | Create a new workflow run |
| GET | `/runs/{id}` | Get run summary with projection |
| GET | `/runs/{id}/events` | List events for a run |
| POST | `/runs/{id}/review` | Submit review decision |
| POST | `/runs/{id}/replay` | Replay a completed run |
| GET | `/runs/{id}/bundle` | Export replay bundle |

## Testing

```bash
make test     # uv run --extra dev pytest -q
make eval     # deterministic workflow golden-case evals
make lint     # uv run --extra dev ruff check + format check
make format   # uv run --extra dev ruff format + fix
```

The current verified baseline is `510 passed, 1 warning` using `make test`.
The current eval baseline is `7/7 passed` using `make eval`.

## Project Structure

```
app/
  main.py             # FastAPI app factory + lifespan DI
  api/                # REST endpoints + Pydantic schemas
  web/                # Jinja2 web UI routes
  templates/          # HTML templates
  core/               # Shared kernel: models, enums, reducer, replay, runners
  workflows/          # Workflow modules (access_request, invoice_intake)
  effects/            # Effect adapters (simulated)
  llm/                # LLM adapters (mock, CLI via claude -p)
  retrieval/          # Document loading, chunking, retrieval, prompt context
  db/                 # SQLite persistence + abstract repositories
tests/
  unit/               # Domain logic tests (parser, validator, policy, reducer)
  integration/        # API + web integration tests (full HTTP lifecycle)
scripts/
  call-claude.py      # Subprocess wrapper for claude -p
  export_bundle.py    # CLI bundle export
```

## Bundle Export

Export a replay bundle for any completed run:

```bash
make export-bundle RUN_ID=<run-id>
```
