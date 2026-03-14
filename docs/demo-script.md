# Demo Script

This guide walks through four demo scenarios that showcase the ai-workflow-engine's core capabilities: automated approval, human review, policy rejection, and deterministic replay.

**Prerequisites:**
- Python >= 3.11 installed
- Run `make install` to install dependencies
- Run `make demo` to start the server at `http://127.0.0.1:8000`

---

## Demo 1: Happy Path (Auto-Approve)

A low-risk access request with a known manager. The system auto-approves and applies a simulated effect.

### Input

```
Please grant John Smith access to the Confluence wiki. His manager is Jane Doe.
```

### Via API

**Step 1:** Create a run:

```bash
curl -s -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"input_text": "Please grant John Smith access to the Confluence wiki. His manager is Jane Doe.", "mode": "LIVE"}'
```

The response includes the run with status `completed` and a projection showing the approved access grant.

**Step 2:** Check the run status:

```bash
curl -s http://127.0.0.1:8000/runs/<RUN_ID>
```

**Step 3:** View the event history:

```bash
curl -s http://127.0.0.1:8000/runs/<RUN_ID>/events
```

Expected event sequence: `run.received` -> `receipt.stored` -> `proposal.parsed` -> `proposal.validated` -> `decision.rendered` -> `effect.simulated` -> `run.completed`.

### Via Web UI

1. Open `http://127.0.0.1:8000/ui/intake`
2. Enter the input text above and select mode "live"
3. Submit the form
4. You are redirected to the run detail page showing status `completed` with all events listed

### Expected Outcome

- The LLM generates a structured proposal receipt
- Validation passes (known system, manager present)
- Policy auto-approves (single low-risk system, standard urgency)
- Simulated effect is applied
- Run reaches `completed` status

---

## Demo 2: Review Path (Human Approval Required)

A request for multiple systems with high urgency triggers the review gate, requiring human approval before effects are applied.

### Input

```
Urgent: Please grant Sarah Lee access to Jira and Confluence immediately. Her manager is Bob Chen.
```

### Via API

**Step 1:** Create a run:

```bash
curl -s -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"input_text": "Urgent: Please grant Sarah Lee access to Jira and Confluence immediately. Her manager is Bob Chen.", "mode": "LIVE"}'
```

The response shows status `review_required` and includes a `review_task`.

**Step 2:** Approve the review:

```bash
curl -s -X POST http://127.0.0.1:8000/runs/<RUN_ID>/review \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve"}'
```

The response shows the run now has status `completed`.

**Step 3:** View updated events:

```bash
curl -s http://127.0.0.1:8000/runs/<RUN_ID>/events
```

### Via Web UI

1. Open `http://127.0.0.1:8000/ui/intake`
2. Enter the input text above and submit
3. The run detail page shows status `review_required` with an approve/reject form
4. Click "Approve"
5. The page refreshes showing status `completed` with the full event history

### Expected Outcome

- Policy flags the request for review (multiple systems + high urgency)
- Run pauses at `review_required` status
- After approval, simulated effect is applied
- Run reaches `completed` status

---

## Demo 3: Rejection Path (Policy Blocks)

A request for a forbidden system is blocked by the policy engine. No effects are applied.

### Input

```
Please grant Alex Kim access to the production database admin panel.
```

### Via API

**Step 1:** Create a run:

```bash
curl -s -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"input_text": "Please grant Alex Kim access to the production database admin panel.", "mode": "LIVE"}'
```

The response shows the run reached a terminal state without approval.

**Step 2:** Verify no effects occurred:

```bash
curl -s http://127.0.0.1:8000/runs/<RUN_ID>/events
```

### Via Web UI

1. Open `http://127.0.0.1:8000/ui/intake`
2. Enter the input text above and submit
3. The run detail page shows the terminal status with no effect events

### Expected Outcome

- The policy engine rejects the request (forbidden system)
- No `effect.simulated` event is emitted
- Run reaches terminal status without any access being granted

---

## Demo 4: Replay (Deterministic Reproduction)

Replay a previously completed run to verify deterministic behavior. The replay reconstructs the final projection from stored events and receipts without reapplying side effects.

### Via API

Using the `RUN_ID` from Demo 1 (the completed happy-path run):

**Step 1:** Replay the run:

```bash
curl -s -X POST http://127.0.0.1:8000/runs/<RUN_ID>/replay
```

The response includes `match: true`, confirming the replayed projection matches the stored projection.

**Step 2:** Export the replay bundle:

```bash
curl -s http://127.0.0.1:8000/runs/<RUN_ID>/bundle
```

Or using the CLI:

```bash
make export-bundle RUN_ID=<RUN_ID>
```

### Via Web UI

1. Navigate to the run detail page: `http://127.0.0.1:8000/ui/runs/<RUN_ID>`
2. Click "Replay"
3. The replay result page shows both the replayed and stored projections with a match indicator

### Expected Outcome

- Replay produces the same final projection as the original run
- No side effects are reapplied during replay
- The replay bundle contains the full run history (events, receipt, projection)
