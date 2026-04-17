# Deploy Scripts

This directory contains the three operational scripts for the SR Voice platform.

## Scripts

### stamp.py — Onboarding: compose + deploy

stamp.py is the main onboarding script. It takes a vertical template and a completed
intake form and produces a live ElevenLabs agent in one command.

**Currently a STUB** — full implementation in Task H (Phase 3).

```bash
python deploy/stamp.py \
  --template plumber/v1 \
  --intake clients/bama-plumbing-intake.json \
  --client-slug bama-plumbing
```

### smoke.py — Testing: run the go-live gate

smoke.py runs the 10-scenario test suite against a deployed agent. The agent must pass
at least 9/10 before client handoff. Used automatically by stamp.py, or run manually.

**Currently a STUB** — full implementation in Task H (Phase 3).

```bash
python deploy/smoke.py \
  --agent-id el_agent_abc123 \
  --template plumber/v1
```

### monitor.py — Production: nightly threshold check

monitor.py is scheduled via Cloud Scheduler to run nightly. It pulls post-call analysis
from ElevenLabs, computes rolling 7-day metrics per client, and alerts via Better Stack
if any threshold is breached.

**Currently a STUB** — full implementation in Task H (Phase 3).

```bash
python deploy/monitor.py --dry-run
```

## Implementation Note

These stubs have complete docstrings, argument parsing, and function contracts. Task H
wires up the actual ElevenLabs API calls, Firestore reads/writes, and Better Stack
alerting. Do not add implementation here — implement in Task H and remove the
`raise NotImplementedError` stubs.
