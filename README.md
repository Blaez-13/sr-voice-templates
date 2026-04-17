# sr-voice-templates

Git-versioned library of vertical templates, prompt fragments, tool schemas, and test scenarios
for the Stellaris Ridge Voice platform. This repo is the source of truth for what deployed
voice agents say and do — not the voice-bot service's database.

> TODO: `git remote add origin https://github.com/Blaez13/sr-voice-templates.git`
> Carl creates the GitHub repo manually, then runs this command in this directory.

## What This Repo Is

Every client voice agent on the SR platform is composed from three inputs:

1. **A vertical template** (e.g. `templates/plumber/v1/`) — defines the conversational workflow,
   which prompts to use, which fragments to include, and what scenarios must pass before go-live.
2. **A fragment library** (`fragments/`) — reusable prompt building blocks that are injected into
   templates in a defined order. Fragments handle cross-cutting concerns: datetime awareness,
   persona, tool usage rules, silence handling, off-topic handling, escalation, PII, output
   format, emergency override, and pricing policy.
3. **A client intake form** (`templates/{vertical}/v1/intake-form.json`) — the client-specific
   values that fill all `{{placeholder}}` markers in the template and fragment files.

The `deploy/stamp.py` script assembles these three inputs and produces a live ElevenLabs agent.

## Repository Layout

```
sr-voice-templates/
  README.md                   — This file
  requirements.txt            — Python dependencies for deploy scripts (PyYAML)
  .gitignore
  fragments/                  — 10 reusable prompt components
    00-datetime-anchor.md     — Current datetime injection + relative date resolution
    01-persona-warm-direct.md — Agent name, tone, and identity constraints
    02-tool-discipline.md     — Tool call sequencing, timeout handling, error translation
    03-silence-handling.md    — What to do when the caller goes quiet
    04-off-topic.md           — How to redirect out-of-scope requests
    05-escalation.md          — When and how to transfer to a human
    06-pii-discipline.md      — What data to collect, what to refuse, how to read back
    07-output-contract.md     — Spoken response format rules + triage data contract
    08-emergency-override.md  — Highest-priority rule: emergency detection + immediate transfer
    09-no-pricing-policy.md   — Never quote prices; redirect to scheduling
  tools/
    get_free_slots.json       — ElevenLabs webhook tool schema for check_availability
    book_appointment.json     — ElevenLabs webhook tool schema for book_appointment
  templates/
    plumber/v1/               — Canonical v1 implementation (complete)
      workflow.yaml           — Node graph, LLM config, fragment order, test config
      prompts/                — 5 node-specific prompt files
      kb/                     — 7 knowledge base files with {{placeholders}}
      tests/simulation/       — 10 YAML test scenarios (01 is fully populated reference)
      intake-form.json        — JSON Schema of all onboarding fields
      README.md               — Deployment guide for plumber vertical
    dental/v1/README.md       — Stub (HIPAA blocker — see notes)
    hvac/v1/README.md         — Stub
    legal/v1/README.md        — Stub
    med-spa/v1/README.md      — Stub (HIPAA blocker — see notes)
  deploy/
    stamp.py                  — Compose + deploy: template + intake → ElevenLabs agent
    smoke.py                  — Run 10-scenario test suite, enforce go-live gate
    monitor.py                — Nightly metric check + Better Stack alerting
    README.md                 — Script usage documentation
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ELEVENLABS_API_KEY` | Yes (smoke.py, stamp.py) | ElevenLabs API key from elevenlabs.io |
| `VOICE_BOT_URL` | No | Voice-bot service base URL. Default: `http://localhost:8080` |

Set these in your shell or a `.env` file (not committed — `.env` is in `.gitignore`).

```bash
export ELEVENLABS_API_KEY=your_key_here
export VOICE_BOT_URL=https://sr-voice-bot-925407339242.us-central1.run.app
```

## Running stamp.py (Deploy a Client Agent)

`stamp.py` takes a template name, a completed intake JSON, and a client slug. It composes
the system prompt from all template nodes (concatenated under `## Section` headers), renders
the knowledge base, calls the voice-bot's `sync-from-template` endpoint to push to
ElevenLabs, and then runs the smoke test suite.

```bash
# Install Python dependencies first
pip install -r requirements.txt

# Deploy a new client (will also run smoke tests after deploy)
python deploy/stamp.py \
  --template plumber/v1 \
  --intake /path/to/bama-plumbing-intake.json \
  --client-slug bama-plumbing

# Dry run — render and preview everything without calling any API
python deploy/stamp.py \
  --template plumber/v1 \
  --intake /path/to/bama-plumbing-intake.json \
  --client-slug bama-plumbing \
  --dry-run

# Deploy without smoke tests (use when iterating on prompts)
python deploy/stamp.py \
  --template plumber/v1 \
  --intake /path/to/intake.json \
  --client-slug bama-plumbing \
  --skip-smoke

# Override voice-bot URL (e.g. staging environment)
python deploy/stamp.py \
  --template plumber/v1 \
  --intake intake.json \
  --client-slug bama-plumbing \
  --voice-bot-url https://staging-vox.run.app
```

### Prompt Architecture: ONE-AGENT-PER-CLIENT

For MVP, `stamp.py` concatenates all per-node prompts (triage, emergency, booking, support,
billing) into a SINGLE ElevenLabs system prompt using `## Section` headers:

```
## Triage

<triage node prompt content>

---

## Emergency

<emergency node prompt content>

---

...
```

The triage node always comes first. Multi-agent Workflow decomposition (independent ElevenLabs
agents per node with Workflow routing) is a v2 concern flagged for Phase 4.

## Running smoke.py (Test Suite)

`smoke.py` runs the 10 simulation scenarios in `tests/simulation/` against a deployed
ElevenLabs agent and writes a JSON report.

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Gate operational and passed >= min_pass scenarios with real results. Safe to go live. |
| `1` | Gate operational, ran real scenarios, but below pass threshold. Do NOT go live. |
| `2` | Gate not operational. Either `API_INTEGRATION_COMPLETE = False` (endpoint not confirmed), or all scenarios are `status: pending` (no `pass_criteria` populated). This is fail-closed by design. |
| `3` | Configuration error: missing agent ID, missing/bad YAML, missing API key, template not found. |

Exit code 2 is distinct from exit 0 (pass) and exit 1 (fail). It signals that the gate
itself cannot run real tests — not that the agent passed or failed. CI pipelines should
treat exit 2 as a blocker that requires human action, not a passing build.

### `gate_status` field in report JSON

The report includes a `gate_status` field alongside the summary:

| Value | When |
|-------|------|
| `"operational"` | API integrated and at least one scenario has `pass_criteria` |
| `"pending_api"` | `API_INTEGRATION_COMPLETE = False` in `smoke.py` |
| `"pending_scenarios"` | API complete but all scenario files have `pass_criteria: null` |

### Usage

```bash
# Run full suite against an agent (min 9/10 required to pass)
python deploy/smoke.py \
  --agent-id el_agent_abc123 \
  --template plumber/v1

# Run a single scenario by ID substring
python deploy/smoke.py \
  --agent-id el_agent_abc123 \
  --template plumber/v1 \
  --scenario 01-flooding-emergency

# Lower the pass threshold for development
python deploy/smoke.py \
  --agent-id el_agent_abc123 \
  --template plumber/v1 \
  --min-pass 5

# Write report to a specific directory
python deploy/smoke.py \
  --agent-id el_agent_abc123 \
  --template plumber/v1 \
  --report-dir /tmp/smoke-reports

# Bypass fail-closed for dev work (all-pending suite exits 0 instead of 2)
python deploy/smoke.py \
  --agent-id el_agent_abc123 \
  --template plumber/v1 \
  --allow-pending
```

**Never use `--allow-pending` in production CI.** It suppresses the fail-closed gate that
prevents unvalidated agents from going live.

### Fail-Closed Behavior

smoke.py is fail-closed on two conditions:

1. **`API_INTEGRATION_COMPLETE = False`** — The ElevenLabs simulation endpoint is not yet
   confirmed. All scenarios run as stubs. Exit 2 (not 0) prevents new agents from passing
   the gate on stub-only results.

2. **All scenarios pending** — A new vertical template with no `pass_criteria` populated
   yet. Without any real assertions, the gate has no evidence the agent works. Exit 2
   forces someone to either populate scenarios or explicitly `--allow-pending` for dev.

This design ensures that the only way to get exit 0 is to have both a working API integration
AND at least `min_pass` scenarios with populated `pass_criteria` that actually pass.

### The JSON Report

```json
{
  "generated_at": "2026-04-16T12:00:00+00:00",
  "gate_status": "operational",
  "summary": { "passed": 9, "failed": 0, "skipped_api_pending": 1, "pending": 0, "total": 10 },
  "api_integration_complete": false,
  "tests": [
    {
      "scenario_id": "01-flooding-emergency",
      "status": "passed",
      "passed": true,
      "failures": []
    }
  ]
}
```

### ElevenLabs Test API Status

The ElevenLabs simulation endpoint (`POST /v1/convai/agents/{agent_id}/simulate`) is not yet
confirmed as publicly available. `smoke.py` has the full assertion logic wired — when the
endpoint is confirmed, set `API_INTEGRATION_COMPLETE = True` in `deploy/smoke.py` and verify
the payload shape matches the TODO comment at the top of the file.

Until then, scenarios run as stubs and the runner exits 2 (gate not operational) by default.
Use `--allow-pending` to suppress exit 2 during local development.

## Admin UI Test Trigger

The voice-bot admin dashboard has a "Run Test Suite" button on the Vox tab for any client
with a provisioned ElevenLabs agent. Click it to:

1. Open a modal showing live streaming output from smoke.py
2. See each scenario result in real time
3. See the final PASS/FAIL badge and report path when complete

The button calls `POST /api/clients/:slug/run-tests` on the voice-bot service, which shells
out to `smoke.py` and streams NDJSON output back to the browser.

The voice-bot service locates `smoke.py` at:
```
<voice-bot-root>/../sr-voice-templates/deploy/smoke.py
```

Both repos must be siblings in the same parent directory (e.g. `Anti-Gravity/`) for this
path to resolve. If they are elsewhere, set the path in `routes/admin/test-runner.js`.

## How to Add a New Scenario YAML

Use `templates/plumber/v1/tests/simulation/01-flooding-emergency.yaml` as the reference
implementation. It is the canonical example of a fully populated scenario.

**Key fields required for an executable scenario:**

```yaml
scenario_id: XX-short-name       # must match the filename prefix
status: ready                    # set to "pending" to skip gracefully
description: >
  One paragraph describing what this test verifies and why it matters.

pass_criteria:
  triage_label: emergency        # or new_booking, billing, service_complaint, etc.
  tool_invoked: classify_service_call
  transfer_fired: true
  max_agent_turns_before_transfer: 2
  must_not_say:
    - "Let me check availability"

tool_mock:
  classify_service_call:
    classification: emergency
    urgency_score: 10

turns:
  - speaker: caller
    text: "The exact words the caller says"
  - speaker: agent
    expected_behavior:
      - What the agent should do (narrative — for human review, not assertion)
```

**Rules:**
- A scenario with `pass_criteria: null` or no `pass_criteria` key is automatically marked
  `pending` by the runner and skipped gracefully (no test failure).
- `status: pending` also forces a skip.
- `tool_mock` overrides what the tool returns for this specific scenario — critical for
  testing edge cases like empty slots or tool failures.
- `expected_behavior` is human-readable documentation, not a machine assertion.
  All machine assertions belong in `pass_criteria`.

## The Compose + Stamp Onboarding Flow

```
                ┌──────────────────────┐
                │   Vertical Template  │
                │   templates/plumber/ │
                │   v1/workflow.yaml   │
                └──────────┬───────────┘
                           │  defines fragment order + KB files
                           ▼
  ┌─────────────┐    ┌─────────────────────────────────────┐
  │  Fragments  │───▶│           stamp.py                  │
  │  fragments/ │    │  1. Validate intake required fields  │
  └─────────────┘    │  2. Render {{placeholders}}          │
                     │  3. Assemble system prompt (all nodes│
  ┌─────────────┐    │     under ## Section headers)        │
  │ Intake Form │───▶│  4. Render KB docs                   │
  │ (per-client │    │  5. POST to voice-bot sync-from-tmpl │
  │  JSON)      │    │  6. Run smoke.py (go-live gate)       │
  └─────────────┘    └──────────────┬──────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │  ElevenLabs Agent     │
                        │  (live, tested)       │
                        └───────────────────────┘
                                    │
                        Twilio number assigned manually
                                    │
                                    ▼
                            Client goes live
```

## Adding a New Vertical

1. Create `templates/{vertical}/v1/` directory structure mirroring `templates/plumber/v1/`
2. Write a `workflow.yaml` specifying which fragments to include and in what order for each node
3. Write vertical-specific prompts (triage, emergency, booking, support, billing)
4. Write KB files with `{{placeholder}}` markers for client-specific content
5. Adapt the emergency criteria in `kb/04-emergency-criteria.md` for the vertical
6. Write 10 simulation scenarios in `tests/simulation/` following the YAML schema above
7. Fill out `intake-form.json` JSON Schema with all fields the vertical needs
8. Test with `stamp.py --dry-run` before provisioning a real agent
9. Update this README

## Adding a New Fragment

1. Create `fragments/{NN}-{slug}.md` with the next available two-digit prefix
2. Write the fragment as a composable markdown block
3. Use `{{placeholder}}` for any runtime variables
4. Document which intake form fields the placeholders map to in the fragment's frontmatter comment
5. Add the fragment to the relevant `workflow.yaml` node definitions in any templates that need it

## Test Scenario YAML Schema

Each file in `tests/simulation/` follows this schema:

```yaml
scenario_id: string         # matches filename prefix (e.g. 01-flooding-emergency)
status: ready|pending       # pending = skip gracefully; ready = execute
description: string         # human-readable description of what this tests
pass_criteria:              # assertions evaluated against agent response
  triage_label: string      # expected classify_service_call classification
  urgency_score_min: int    # minimum urgency_score in tool payload
  tool_invoked: string      # name of tool that must be called
  tool_invoked_2: string    # second required tool call
  transfer_fired: bool      # whether transfer_to_number must be called
  booking_confirmed: bool   # whether book_appointment returned confirmed=true
  max_agent_turns_before_transfer: int
  max_turns_to_booking: int
  required_fields_collected: [string]  # must appear in tool call args
  must_not_say: [string]    # phrases that, if spoken, cause the test to fail
  must_say_one_of: [string] # at least one phrase from this list must appear
tool_mock:                  # optional: override tool responses for this scenario
  classify_service_call:
    classification: emergency
    urgency_score: 10
turns:                      # the simulated conversation
  - speaker: caller|agent
    text: string            # caller's exact words (caller turns only)
    expected_behavior: string|list  # narrative description (agent turns)
```

All `expected_behavior` entries are narrative — smoke.py evaluates `pass_criteria`
programmatically and uses `expected_behavior` as documentation for human reviewers
when a test fails.

## Placeholder Conventions

- `{{client_name}}` — business display name
- `{{agent_name}}` — AI agent name (e.g. "Vox", "Alex")
- `{{current_datetime}}` — injected at runtime by fragment 00
- `{{business_timezone}}` — IANA timezone string
- `{{emergency_phone}}` — on-call emergency number
- `{{escalation_phone}}` — general transfer number
- `{{service_area_primary}}` — plain-English service area description
- `{{client_slug}}` — URL-safe business identifier
- `{{webhook_base_url}}` — base URL of SR voice-bot service

All placeholders map to fields in the vertical's `intake-form.json`.

## LLM and TTS Configuration

Per decision D7 in `2026-04-16-sr-voice-elevenlabs-pivot.md`:

| Node | Model | Rationale |
|---|---|---|
| Triage, emergency, support | Gemini 2.0 Flash Lite | Speed, cost |
| Booking, billing | Gemini 2.0 Flash | Tool-call reliability |
| Post-call analysis | Claude Sonnet 4-6 | Quality (async, off hot path) |

TTS: ElevenLabs Flash v2.5. Temperature 0.7, reasoning_effort low on all nodes.

## Related Repos

- `github.com/Blaez13/vox` — SR voice-bot service (webhook handler, Firestore, admin UI)
- Branch `refactor/elevenlabs-source-of-truth` — the refactor that makes this repo the
  authoritative source for agent configuration
