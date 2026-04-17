# Plumber v1 — Template Documentation

This is the canonical v1 voice agent template for plumbing businesses. It is the first fully-implemented vertical in the SR Voice platform and serves as the reference pattern for all subsequent verticals.

## What a Deployed Plumber Agent Does

When a caller dials a plumbing business running this template, they reach an AI receptionist (Vox) that:

1. **Greets the caller** and reads a 911 disclaimer at call start
2. **Triages the call** by listening to the caller's issue and invoking `classify_service_call`
3. **Routes to the appropriate node** based on classification:
   - Emergency (flooding, sewage, gas) → immediate transfer to on-call line in <10 seconds
   - New service request → booking flow (check availability, collect info, confirm, book)
   - Complaint or urgent follow-up → support flow (empathy, capture details, service request)
   - Billing question → billing flow (verify identity, answer policy, transfer for account details)
4. **Uses 4 tools** via webhook to the SR voice-bot service:
   - `check_availability` — checks the GHL calendar for open slots
   - `book_appointment` — creates the appointment in GHL
   - `classify_service_call` — routes based on urgency and intent
   - `create_service_request` — logs tickets and pages the owner
5. **Never quotes prices**, invents availability, or confirms failed bookings
6. **Transfers to a human** when the caller requests it, the situation exceeds its scope, or tools fail twice

## Onboarding a New Plumber Client

### Step 1 — Fill the intake form

Copy `intake-form.json` and fill all required fields:
```
cp templates/plumber/v1/intake-form.json clients/my-client-intake.json
# Edit my-client-intake.json with client-specific values
```

Key fields to fill:
- `client_slug`, `client_name`, `agent_name`
- `voice_id` (choose from ElevenLabs voice library)
- `webhook_base_url` (your deployed SR voice-bot URL)
- `tool_secret` (generate: `openssl rand -hex 32`, store in Secret Manager)
- `emergency_phone`, `business_hours`, `service_area_zips`
- All SLA commitments and escalation contacts

### Step 2 — Run stamp.py

```bash
python deploy/stamp.py \
  --template plumber/v1 \
  --intake clients/my-client-intake.json \
  --client-slug my-client-slug
```

stamp.py will:
- Assemble all prompt fragments per `workflow.yaml`
- Render `{{placeholders}}` using the intake form values
- Upload the KB files to ElevenLabs as a knowledge base
- Create/update the ElevenLabs agent with the assembled system prompt
- Upload the tool schemas (with rendered webhook URLs)
- Run smoke.py against the new agent ID

### Step 3 — Review smoke test results

smoke.py runs all 10 scenarios from `tests/simulation/`. The agent must pass 9/10 before go-live. Review the report at `./reports/smoke-{timestamp}.json`.

### Step 4 — Configure Twilio

Assign the client's Twilio number to point to the ElevenLabs agent. (Manual step — see main voice-bot runbook.)

## File Map

```
plumber/v1/
  workflow.yaml         — Node graph, LLM assignments, fragment order, tool list
  prompts/
    triage.md           — Entry point: classify, route, handle emergencies
    emergency.md        — Transfer immediately, 911 disclaimer
    booking.md          — check_availability → collect info → book_appointment
    support.md          — Complaint/urgent follow-up → service request
    billing.md          — Verify identity → answer policy → transfer for details
  kb/
    01-service-area.md  — Where the business operates
    02-hours-and-after-hours.md — Hours, after-hours routing
    03-pricing-policy.md — No quoting, dispatch fee, payment methods
    04-emergency-criteria.md — Exact keywords and urgency thresholds
    05-services-offered.md — Service list with service_id values
    06-common-faqs.md  — Pre-answered common questions
    07-escalation-contacts.md — Phone numbers, callback SLAs
  tests/simulation/     — 10 YAML scenarios, all must pass before go-live
  intake-form.json      — JSON Schema of all client-specific values
```

## Customization Points

- **Emergency keywords** — extend `kb/04-emergency-criteria.md` with client-specific triggers
- **Service list** — replace the default service table in `intake-form.json` services_list
- **After-hours policy** — set `after_hours_policy` in intake form (3 options)
- **Agent persona** — `agent_name` in intake form; voice selected via `voice_id`
- **Pricing disclosure** — `dispatch_fee_policy` in intake form

## LLM Configuration (from workflow.yaml)

- Triage, emergency, support: Gemini 2.0 Flash Lite (speed + cost)
- Booking, billing: Gemini 2.0 Flash (tool-call reliability)
- TTS: ElevenLabs Flash v2.5
- Temperature: 0.7, reasoning_effort: low on all nodes
