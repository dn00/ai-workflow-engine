# ai-workflow-engine

**Deterministic AI Workflow Automation**

Built a production-shaped AI workflow automation system that converts unstructured access requests into safe, replayable, auditable actions using LLM proposal receipts, deterministic policy gates, append-only events, and resumable workflow runners.

## Quick Start

**Prerequisites:** Python >= 3.11

```bash
# Install dependencies
make install

# Start the demo server
make demo
```

The server starts at `http://127.0.0.1:8000`. Open `http://127.0.0.1:8000/ui/intake` for the web UI.

## Demo

The demo showcases four scenarios that exercise the full workflow lifecycle:

1. **Happy path** — auto-approved access request with simulated effect
2. **Review path** — multi-system request requiring human approval
3. **Rejection path** — forbidden system blocked by policy
4. **Replay** — deterministic reproduction of a prior run

Run `make demo` to start the server, then follow the step-by-step instructions in [docs/demo-script.md](docs/demo-script.md).

## Architecture

The system uses a four-layer architecture where LLMs propose and deterministic code decides:

| Layer | Responsibility |
|-------|---------------|
| **Layer 4 — API / UX** | FastAPI endpoints, Jinja2 web UI |
| **Layer 3 — Runtime** | LocalRunner orchestration, mode handling |
| **Layer 2 — Domain Engine** | Parser, validator, policy, reducer |
| **Layer 1 — Persistence** | SQLite repositories, append-only events |

Each layer depends only on layers below it. All domain logic is pure — no I/O, no side effects.

For the full architecture overview including data flow, extension seams, and directory structure, see [docs/architecture.md](docs/architecture.md).

## Testing

```bash
# Run the full test suite
make test

# Run linting
make lint

# Auto-format code
make format
```

## Project Structure

```
app/
  api/          # REST API endpoints
  web/          # Web UI routes
  templates/    # Jinja2 templates
  core/         # Shared kernel (events, runners, replay, projections)
  workflows/    # Workflow-specific modules (access_request)
  effects/      # Effect adapters (simulated)
  db/           # Persistence layer (SQLite)
  llm/          # LLM adapter interface
tests/
  unit/         # Unit tests
  integration/  # Integration tests
docs/
  demo-script.md    # Demo walkthrough
  architecture.md   # Architecture overview
```

## Bundle Export

Export a replay bundle for any completed run:

```bash
make export-bundle RUN_ID=<run-id>
```
