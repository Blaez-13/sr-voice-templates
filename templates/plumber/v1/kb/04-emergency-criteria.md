# Emergency Criteria — Plumber

This file defines what constitutes a plumbing emergency for {{client_name}}.
These criteria are injected into the `classify_service_call` tool's urgency_definitions parameter at provisioning.

## Confirmed Emergencies (transfer immediately, urgency_score 9–10)

- Active water flooding inside the building with no shutoff identified
- Sewage or raw waste backing up into the home or business
- Suspected gas leak (gas smell near water heater, pipes, or appliances)
- Burst pipe with water actively flowing
- Water heater leaking rapidly or making banging/hissing sounds
- No water at all in the building (full loss of service)
- Frozen pipe that the caller believes has already burst

## Urgent (same-day service, urgency_score 6–8)

- Slow drain backup affecting multiple fixtures
- Running toilet causing visible water waste
- Water heater producing no hot water (no safety risk — comfort issue)
- Visible leak under sink or from appliance connections (not flooding)
- Leaking outdoor faucet
- Toilet running constantly (not overflowing)

## Non-Urgent (schedule normally, urgency_score 1–5)

- General maintenance inspection
- Water softener service
- New fixture installation (faucet, toilet, showerhead)
- Water pressure complaints (not zero pressure)
- Remodel or renovation plumbing

## Ambiguous Keyword Handling

If the caller says "water on the floor" or "something is leaking" without specifying severity:
Ask ONE question: "Is the water actively flowing or spreading right now?"
- Yes → treat as emergency
- No → route to urgent booking

## Emergency Contact for This Client

Emergency on-call: {{emergency_phone}}
Emergency hours: {{emergency_hours}}
