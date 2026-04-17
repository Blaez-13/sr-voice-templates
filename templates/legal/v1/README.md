# Legal v1 — Template Stub

TODO: populate in v2

## Notes for Future Implementation

- Intake-only use case: agent captures caller name, contact info, and brief matter description. Agent does NOT provide legal advice.
- Must include prominent disclaimer at call start: "I'm an AI receptionist — I cannot give legal advice."
- No billing inquiry handling (handled by firm directly).
- Emergency path: criminal matter where caller has been arrested or is in custody → transfer immediately.
- Practice area routing: if firm has multiple practice areas, triage must route to the correct intake queue.
- Confidentiality caveat: all calls should be treated as potentially privileged — agent does not record or repeat sensitive legal facts beyond what is needed for intake.
- Use plumber/v1 as structural reference, remove all service/emergency plumbing content.
