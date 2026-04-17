# Dental v1 — Template Stub

TODO: populate in v2

## Notes for Future Implementation

- HIPAA compliance required before deployment. Requires ElevenLabs Enterprise tier + BAA. See decision D10 in `2026-04-16-sr-voice-elevenlabs-pivot.md` — deferred until Enterprise pricing is modeled.
- Emergency criteria differ from plumber: dental emergencies include severe tooth pain, lost permanent tooth, jaw injury, abscess with swelling.
- Booking flow must accommodate appointment types (cleaning, exam, emergency, new patient) with different durations.
- PII discipline must be stricter — no PHI over voice; intake captures name and callback only.
- Use plumber/v1 as the structural reference — same fragment library, same tool schemas, different KB and emergency criteria.
