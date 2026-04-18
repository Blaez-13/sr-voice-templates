# sr-demo / v1 — Self-Selling Demo Agent (Samantha)

**Not a receptionist.** This is a sales agent that pretends to be a receptionist during Phase 4 (role-play), then pitches the AI receptionist service in Phase 6 and books an activation call in Phase 7.

Based on the publicly-shared "Watch this AI sell itself for $497 a month" prompt, adapted for SR's stack (ElevenLabs single-agent architecture, Firestore client registry, per-client GHL calendar).

## How it's different from `_base/v1`

| Dimension | `_base/v1` | `sr-demo/v1` |
|---|---|---|
| Role | Client's receptionist | SR's own sales rep |
| Who it serves | The client's inbound callers | Prospects SR wants to sell to |
| Calendar target | The client's GHL calendar | SR's own GHL calendar |
| Phase structure | Freeform — prompt routes naturally | Strict 8-phase sequence with verbal bridges |
| Tool calls | Any time a booking/message/transfer is needed | Phase 4 booking is SIMULATED (no tool calls); Phase 7 is the only real booking phase |
| Price pitch | None | $497/mo with 30-day free trial |
| Typical call length | 1–3 min | 5–8 min |

## Who deploys this

SR itself. Jarod sends outbound prospects to a phone number attached to a `sr-demo`-provisioned EL agent. Phase 7 books into SR's GHL calendar so Carl and Jarod see the activation calls.

If another agency wanted to run a similar demo for their own sales, they could provision this template under their own client slug, with their own calendar, their own activation team name, etc.

## Intake fields

Minimal (11 required, most defaulted):

- `client_slug` — e.g. `sr-demo`
- `client_name` — agency name (`Stellaris Ridge`)
- `agent_name` — `Samantha` by default
- `voice_id` — ElevenLabs voice for the agent
- `webhook_base_url` — voice-bot service URL (auto-detected at provision)
- `tool_secret` — auto-injected from `ELEVENLABS_TOOL_SECRET` env
- `business_timezone` — defaults `America/Chicago`
- `activation_team` — e.g. `Carl or Jarod`
- `price_monthly` — `497` default
- `trial_days` — `30` default
- `first_message` — defaulted to the Samantha intro

## Known gaps

- **Knowledge base is empty.** The prompt references an NEPQ framework and objection-handling scripts in a knowledgebase. The agent will improvise without them; populating the KB is a future improvement. Carl has the creator's full prompt set coming.
- **Phase 4 vs Phase 7 booking discipline is prompt-only.** The `book_appointment` tool doesn't know whether it's being called during a simulated demo or a real activation booking. The prompt explicitly instructs the agent not to call the tool during Phase 4 — if it slips, SR's calendar would get polluted with fake bookings.
- **Price and trial are literals.** `$497` and `30 days` are hardcoded via intake placeholders. Changing mid-deploy means re-applying the template.
- **No post-call follow-up.** No SMS confirmation, no nurture sequence, no CRM push beyond the GHL booking itself.

## Provisioning

Through the admin UI:
1. Create a new client with slug `sr-demo` (or whatever agency is deploying it).
2. Set GHL credentials to the agency's own calendar.
3. Click **Apply Industry Template**, select `sr-demo v1`.
4. Fill the intake (most defaults are fine for SR).
5. Attach a phone number to the provisioned EL agent in the EL console.
