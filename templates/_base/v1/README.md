# _base / v1 — Generic Single-Agent Template

This is the starting point every new SR client uses. It's vertical-agnostic: a generic business receptionist that can book appointments, answer questions from the knowledge base, take callback messages, and qualify-then-transfer to a human.

## When to use `_base` vs a vertical template

- **Use `_base`** for most clients — marketing agencies, consultants, local service businesses with standard hours and one primary calendar.
- **Use a vertical template** (`plumber`, `hvac`, `dental`, `legal`, `med-spa`) when the business has industry-specific needs:
  - Emergency dispatch rules (plumbing, HVAC)
  - 911 disclaimer required (medical, dental)
  - Billing department routing (legal, dental)
  - Spanish-language dispatch (any service vertical with bilingual staff)

## Architecture

**Single-agent.** One ElevenLabs agent per client, one LLM node, one assembled system prompt. Routing happens inside the prompt via the qualification-first pattern (see `../../fragments/10-escalation-qualify-first.md`).

This replaces the earlier multi-subagent workflow design. Carl's call during the 2026-04-17 architecture review: "most people will work off of one calendar… having the agent being the same and not being passed on simplifies things." See `C:/Stellaris/10-stellaris-ridge/_decisions.md` → 2026-04-17.

## Files

```
templates/_base/v1/
├── README.md                  — you are here
├── workflow.yaml              — tells stamp.py how to assemble the agent
├── intake-form.json           — the minimum fields needed at onboarding
├── prompts/
│   └── agent.md               — the main system prompt template
└── kb/
    ├── 01-about-business.md   — overview + service area + contact
    ├── 02-hours-and-contact.md — hours, escalation routing
    ├── 03-services-and-pricing.md — what the business offers
    └── 04-faq.md              — common questions (fill from client's existing FAQ)
```

## Intake

At minimum, onboarding needs:

| Field | Example |
|-------|---------|
| `client_slug` | `acme-consulting` |
| `client_name` | `Acme Consulting` |
| `agent_name` | `Ridge` (default) |
| `voice_id` | ElevenLabs voice ID |
| `business_timezone` | `America/Chicago` |
| `business_hours` | `Monday–Friday 9–5` |
| `main_phone` | `+12055551234` |
| `escalation_phone` | `+12055551235` (where transfers go) |
| `owner_name` | `Jane` |
| `owner_email` | `jane@acme.com` (for take_message email alerts) |
| `owner_phone` | `+12055550100` (for take_message SMS alerts) |
| `services_summary` | 1–3 sentence description |
| `first_message` | Greeting |

Full schema: `intake-form.json`.

## Tools the agent gets

All provisioned automatically by `lib/elevenlabs-tools.js` at agent-creation time:

- `check_availability(date)` — check open appointment slots
- `book_appointment(slotTime, firstName, ...)` — book a confirmed slot
- `take_message(firstName, phone, reason, urgency)` — capture callback requests with Postmark email + Twilio SMS fan-out
- `transfer_to_number` — ElevenLabs built-in, wired to `escalation_phone`
- `end_call` — ElevenLabs built-in

## Stamping a client from this template

From the `sr-voice-templates/` repo root:

```bash
python deploy/stamp.py \
  --template _base/v1 \
  --intake intake-acme.json \
  --client-slug acme-consulting \
  --voice-bot-url https://sr-voice-bot-925407339242.us-central1.run.app
```

stamp.py will:
1. Validate the intake JSON against `intake-form.json`
2. Read `workflow.yaml` and assemble the full system prompt from fragments + `prompts/agent.md`
3. Render placeholders in the KB files
4. POST to the voice-bot's `/api/clients/<slug>/elevenlabs/sync-from-template` endpoint, which:
   - Creates or patches the EL agent
   - Uploads the rendered KB docs
   - Stores `industry_template_ref: "_base/v1"` in Firestore

## Extending this template

If a client needs something `_base` doesn't cover, options in order of preference:

1. **Add a knowledge base file** for vertical-specific content (services, pricing, policies). No prompt changes needed — the agent reads KB at runtime.
2. **Override a fragment** by pointing `workflow.yaml` at a replacement fragment. Example: `plumber/v1` replaces `04-off-topic.md` with a plumbing-specific one.
3. **Create a vertical template** if the client belongs to a category that will recur (plumbers, dentists, etc.). Copy `_base/v1/` to `<vertical>/v1/`, then override `workflow.yaml` and prompts as needed.

Do NOT edit `_base/v1/*` to fix a single-client issue. Keep `_base` clean and universal; specialization goes in vertical templates or per-client overrides.
