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
      tests/simulation/       — 10 YAML test scenarios
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
  │  fragments/ │    │  1. Render {{placeholders}}          │
  └─────────────┘    │  2. Assemble system prompt           │
                     │  3. Upload KB to ElevenLabs          │
  ┌─────────────┐    │  4. Render + upload tool schemas     │
  │ Intake Form │───▶│  5. Create/update EL agent           │
  │ (per-client │    │  6. Run smoke.py (pass gate)         │
  │  JSON)      │    └──────────────┬──────────────────────┘
  └─────────────┘                   │
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
6. Write 10 simulation scenarios in `tests/simulation/` following the YAML schema from plumber/v1
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
description: string         # human-readable description of what this tests
pass_criteria:              # assertions evaluated against agent response
  triage_label: string      # expected classify_service_call classification
  urgency_score_min: int    # minimum urgency_score in tool payload
  tool_invoked: string      # name of tool that must be called
  transfer_fired: bool      # whether transfer_to_number must be called
  max_agent_turns_before_transfer: int
  must_not_say: [string]    # phrases that, if spoken, cause the test to fail
  must_say_one_of: [string] # at least one phrase from this list must appear
tool_mock:                  # optional: override tool responses for this scenario
  check_availability:
    response: {...}
  book_appointment:
    first_call_response: {...}
    second_call_response: {...}
turns:                      # the simulated conversation
  - speaker: caller|agent
    text: string            # caller's exact words
    expected_behavior: string|list  # narrative description of what agent should do
```

All `expected_behavior` entries are narrative — smoke.py evaluates `pass_criteria` programmatically
and uses `expected_behavior` as documentation for the human reviewer when a test fails.

## Placeholder Conventions

- `{{client_name}}` — business display name
- `{{agent_name}}` — AI agent name (e.g. "Vox", "Alex")
- `{{current_datetime}}` — injected at runtime by fragment 00
- `{{business_timezone}}` — IANA timezone string
- `{{emergency_phone}}` — on-call emergency number
- `{{escalation_phone}}` — general transfer number
- `{{service_area}}` — plain-English service area description
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
