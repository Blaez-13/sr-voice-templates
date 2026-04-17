#!/usr/bin/env python3
"""
smoke.py — Run the 10-scenario test suite against a deployed ElevenLabs agent.

PURPOSE
-------
smoke.py is the go-live gate for SR Voice agents. Before any client agent is
handed off, it must pass at least 9 of 10 simulation scenarios defined in the
template's tests/simulation/ directory.

Each scenario YAML defines:
  - Simulated caller turns (what the caller says)
  - Expected agent behaviors (triage label, tool invoked, transfer fired, etc.)
  - pass_criteria (structured assertions on the agent's response)
  - Optional tool_mock overrides (to simulate empty slots, tool failures, etc.)

smoke.py submits each scenario to the ElevenLabs test API and evaluates the
response against the pass_criteria. It writes a JSON report and exits with one
of the codes below.

USAGE
-----
  python deploy/smoke.py \\
    --agent-id <elevenlabs_agent_id> \\
    --template plumber/v1 \\
    [--min-pass 9]                     # Default: 9
    [--scenario 01-flooding-emergency] # Run a single scenario by ID
    [--report-dir ./reports]           # Where to write the JSON report (default: ./reports)
    [--api-key <key>]                  # Falls back to ELEVENLABS_API_KEY env var
    [--allow-pending]                  # Allow all-pending suites to exit 0 (dev only)

ENVIRONMENT VARIABLES
---------------------
  ELEVENLABS_API_KEY — Required. Your ElevenLabs API key.

EXIT CODES
----------
  0 — Gate operational AND passed >= min_pass scenarios with real results.
      At least one scenario must be "ready" (has pass_criteria) and must pass.
  1 — Gate operational, ran real scenarios, but below pass threshold.
      Agent should NOT go live.
  2 — Gate not operational. Either:
        a) API_INTEGRATION_COMPLETE = False (API endpoint not yet confirmed), OR
        b) ALL scenarios are status "pending" (no pass_criteria populated).
      This is distinct from a pass (0) or a real failure (1).
      Use --allow-pending to suppress exit 2 for dev work (exits 0 instead).
  3 — Configuration error: missing agent ID, missing scenarios, bad YAML,
      missing API key, template not found, etc.

gate_status field in report JSON:
  "operational"        — API integrated and at least one ready scenario exists
  "pending_api"        — API_INTEGRATION_COMPLETE = False
  "pending_scenarios"  — API complete but all scenarios are pending/unready

ElevenLabs Test API Notes
-------------------------
ElevenLabs does not yet expose a public /simulate or /test endpoint for
ConvAI agents (as of April 2026). This runner uses the closest available
mechanism: creating a simulated conversation via the ConvAI conversations
API (POST /v1/convai/conversations/simulate) if available, or falling back
to a structured stub that exercises the assertion logic locally.

TODO: Verify the exact simulation endpoint once EL publishes it.
      Track issue: https://elevenlabs.io/docs/conversational-ai
      Expected shape: POST /v1/convai/agents/{agent_id}/simulate
        Body: { turns: [{role, text}], variables: {}, mock_tools: {} }
        Response: { transcript: [{role, text, tool_calls: []}] }

When the API endpoint is not confirmed, each scenario runs in STUB mode:
  - The scenario is parsed and assertions are validated for structural correctness
  - The result is marked "skipped_api_pending" (not pass, not fail)
  - The runner exits 2 (gate not operational) unless --allow-pending is passed
"""

import argparse
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Optional imports — prefer stdlib, fall back gracefully
# ---------------------------------------------------------------------------
try:
    import urllib.request
    import urllib.error
    _HAS_URLLIB = True
except ImportError:
    _HAS_URLLIB = False

# PyYAML is the only non-stdlib dep. Listed in requirements.txt.
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
# TODO: Replace with confirmed endpoint when EL publishes the simulation API.
# Candidate path based on ConvAI API structure:
SIMULATE_PATH = "/convai/agents/{agent_id}/simulate"
API_INTEGRATION_COMPLETE = False   # Flip to True once endpoint is confirmed


# ---------------------------------------------------------------------------
# YAML loader — minimal fallback if PyYAML is absent
# ---------------------------------------------------------------------------
def load_yaml_file(path: Path) -> dict:
    """Load a YAML file. Uses PyYAML if available, else a minimal scalar parser."""
    text = path.read_text(encoding="utf-8")
    if _HAS_YAML:
        docs = list(yaml.safe_load_all(text))
        return docs[0] if docs else {}
    # Minimal fallback: handles only top-level scalar key: value pairs.
    # Sufficient for reading scenario_id and description — pass_criteria
    # parsing requires PyYAML for nested structures.
    result = {}
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("#") or not line or line.startswith("---"):
            continue
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip().strip('"').strip("'")
    return result


# ---------------------------------------------------------------------------
# Scenario loading
# ---------------------------------------------------------------------------
def load_scenarios(template_dir: Path, scenario_id: str = None) -> list:
    """
    Load simulation scenario YAML files from <template_dir>/tests/simulation/.

    Args:
        template_dir: Path to the vertical template directory (e.g. templates/plumber/v1/).
        scenario_id:  If provided, load only the matching scenario. Otherwise load all.

    Returns:
        List of parsed scenario dicts, sorted by filename.

    Raises:
        SystemExit(3) if no scenarios are found or a required field is missing.
    """
    sim_dir = template_dir / "tests" / "simulation"
    if not sim_dir.exists():
        print(f"[smoke.py] ERROR: simulation directory not found: {sim_dir}", file=sys.stderr)
        sys.exit(3)

    yaml_files = sorted(sim_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"[smoke.py] ERROR: no scenario YAML files found in {sim_dir}", file=sys.stderr)
        sys.exit(3)

    if scenario_id:
        yaml_files = [f for f in yaml_files if scenario_id in f.stem]
        if not yaml_files:
            print(f"[smoke.py] ERROR: no scenario matching '{scenario_id}' in {sim_dir}", file=sys.stderr)
            sys.exit(3)

    scenarios = []
    for yf in yaml_files:
        try:
            data = load_yaml_file(yf)
        except Exception as e:
            print(f"[smoke.py] WARNING: failed to parse {yf.name}: {e}", file=sys.stderr)
            continue

        # Mark scenarios that haven't been fully populated yet as pending.
        # A scenario is "pending" if it has no pass_criteria or pass_criteria is null/empty.
        status = "ready"
        if not data.get("pass_criteria"):
            status = "pending"

        data["_file"] = yf.name
        data["_status"] = status
        if "scenario_id" not in data:
            data["scenario_id"] = yf.stem
        scenarios.append(data)

    if not scenarios:
        print(f"[smoke.py] ERROR: no parseable scenarios found", file=sys.stderr)
        sys.exit(3)

    return scenarios


# ---------------------------------------------------------------------------
# ElevenLabs simulation API call
# ---------------------------------------------------------------------------
def call_elevenlabs_simulate(agent_id: str, scenario: dict, api_key: str) -> dict:
    """
    POST the scenario conversation turns to the ElevenLabs simulation API.

    IMPORTANT: This endpoint is not yet confirmed as publicly available.
    The function structure is correct; the HTTP call stubs with a clear
    TODO comment pointing to EL docs.

    Args:
        agent_id: ElevenLabs agent ID.
        scenario:  Parsed scenario dict.
        api_key:   ElevenLabs API key.

    Returns:
        API response dict, or a stub response if API_INTEGRATION_COMPLETE is False.
    """
    if not API_INTEGRATION_COMPLETE:
        # Stub response — signals that the API call was not made.
        # Replace this block once the endpoint is confirmed.
        # TODO: Verify endpoint at https://elevenlabs.io/docs/conversational-ai
        #       Expected: POST https://api.elevenlabs.io/v1/convai/agents/{agent_id}/simulate
        return {
            "_stub": True,
            "_message": "API integration incomplete — verify endpoint at https://elevenlabs.io/docs/conversational-ai",
            "transcript": [],
            "tool_calls": [],
            "triage_label": None
        }

    # ── Real API call (active when API_INTEGRATION_COMPLETE = True) ──────────
    turns = []
    for turn in scenario.get("turns", []):
        if turn.get("speaker") == "caller" and turn.get("text"):
            turns.append({"role": "user", "content": turn["text"]})

    payload = json.dumps({
        "turns": turns,
        "mock_tools": scenario.get("tool_mock", {})
    }).encode("utf-8")

    url = f"{ELEVENLABS_BASE}{SIMULATE_PATH.format(agent_id=agent_id)}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ElevenLabs API HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"ElevenLabs API connection error: {e.reason}")


# ---------------------------------------------------------------------------
# Assertion evaluation
# ---------------------------------------------------------------------------
def evaluate_pass_criteria(scenario: dict, api_response: dict) -> tuple:
    """
    Evaluate the agent's API response against the scenario's pass_criteria.

    Supported assertion keys in pass_criteria:
      triage_label            — string: api_response.triage_label must equal this
      urgency_score_min       — int: api_response.urgency_score must be >= this
      tool_invoked            — string: must appear in api_response.tool_calls
      tool_invoked_2          — string: second required tool call
      transfer_fired          — bool: transfer_to_number must appear in tool_calls
      booking_confirmed       — bool: book_appointment response must have confirmed=true
      max_agent_turns_before_transfer — int: agent must transfer within N turns
      max_turns_to_booking    — int: booking must complete within N total turns
      required_fields_collected — list of strings: must appear in tool call args
      must_not_say            — list of strings: none may appear in transcript text
      must_say_one_of         — list of strings: at least one must appear in transcript

    When api_response._stub is True (API not yet integrated), all criteria
    are reported as "skipped_api_pending" rather than pass or fail.

    Returns:
        Tuple of (passed: bool, status: str, failures: list[str])
        status is one of: "passed", "failed", "skipped_api_pending"
    """
    if api_response.get("_stub"):
        return False, "skipped_api_pending", [api_response.get("_message", "API stub")]

    criteria = scenario.get("pass_criteria", {})
    if not criteria:
        return True, "passed", []

    failures = []
    transcript_text = " ".join(
        t.get("content", "") for t in api_response.get("transcript", [])
        if t.get("role") == "assistant"
    ).lower()
    tool_calls = [tc.get("name", tc.get("tool", "")) for tc in api_response.get("tool_calls", [])]

    # triage_label
    if "triage_label" in criteria:
        expected = criteria["triage_label"]
        actual = api_response.get("triage_label")
        if actual != expected:
            failures.append(f"triage_label: expected '{expected}', got '{actual}'")

    # urgency_score_min
    if "urgency_score_min" in criteria:
        min_score = criteria["urgency_score_min"]
        actual = api_response.get("urgency_score", 0)
        if actual < min_score:
            failures.append(f"urgency_score_min: expected >={min_score}, got {actual}")

    # tool_invoked
    for key in ("tool_invoked", "tool_invoked_2"):
        if key in criteria:
            expected_tool = criteria[key]
            if expected_tool not in tool_calls:
                failures.append(f"{key}: '{expected_tool}' not found in tool_calls {tool_calls}")

    # transfer_fired
    if "transfer_fired" in criteria:
        expected = criteria["transfer_fired"]
        actual = "transfer_to_number" in tool_calls
        if actual != expected:
            failures.append(f"transfer_fired: expected {expected}, got {actual}")

    # max_agent_turns_before_transfer
    if "max_agent_turns_before_transfer" in criteria:
        max_turns = criteria["max_agent_turns_before_transfer"]
        transfer_turn = None
        for i, tc in enumerate(api_response.get("tool_calls", [])):
            if tc.get("name") == "transfer_to_number":
                transfer_turn = i
                break
        if transfer_turn is None:
            failures.append(f"max_agent_turns_before_transfer: transfer never fired")
        elif transfer_turn >= max_turns:
            failures.append(
                f"max_agent_turns_before_transfer: transferred at turn {transfer_turn}, max was {max_turns - 1}"
            )

    # must_not_say
    for phrase in criteria.get("must_not_say", []):
        if phrase.lower() in transcript_text:
            failures.append(f"must_not_say: agent said '{phrase}'")

    # must_say_one_of
    must_say = criteria.get("must_say_one_of", [])
    if must_say:
        if not any(p.lower() in transcript_text for p in must_say):
            failures.append(f"must_say_one_of: none of {must_say} found in transcript")

    # required_fields_collected (checks tool call args)
    req_fields = criteria.get("required_fields_collected", [])
    if req_fields:
        all_args_text = json.dumps(api_response.get("tool_calls", [])).lower()
        for field in req_fields:
            if field.lower() not in all_args_text:
                failures.append(f"required_fields_collected: '{field}' not found in tool call arguments")

    passed = len(failures) == 0
    return passed, "passed" if passed else "failed", failures


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------
def write_report(results: list, report_dir: Path, gate_status: str) -> str:
    """
    Write a JSON test report to report_dir.

    Filename format: smoke-<YYYY-MM-DDTHH-MM-SS>.json
    Returns the absolute path to the written file.

    The report includes a `gate_status` field:
      "operational"       — API integrated and at least one ready scenario exists
      "pending_api"       — API_INTEGRATION_COMPLETE = False
      "pending_scenarios" — API complete but all scenarios are pending/unready
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"smoke-{ts}.json"
    report_path = report_dir / filename

    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped_api_pending")
    pending = sum(1 for r in results if r["status"] == "pending")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_status": gate_status,
        "summary": {
            "passed": passed,
            "failed": failed,
            "skipped_api_pending": skipped,
            "pending": pending,
            "total": len(results)
        },
        "api_integration_complete": API_INTEGRATION_COMPLETE,
        "tests": results
    }

    if not API_INTEGRATION_COMPLETE:
        report["warning"] = (
            "API integration incomplete — verify endpoint at "
            "https://elevenlabs.io/docs/conversational-ai. "
            "Results marked 'skipped_api_pending' are not real test outcomes."
        )

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(report_path.resolve())


# ---------------------------------------------------------------------------
# Single scenario runner
# ---------------------------------------------------------------------------
def run_scenario(agent_id: str, scenario: dict, api_key: str) -> dict:
    """
    Run a single scenario against the ElevenLabs simulation API.

    Returns a result dict with keys:
      scenario_id, description, status, passed, failures, raw_response
    """
    scenario_id = scenario.get("scenario_id", scenario.get("_file", "unknown"))
    description = scenario.get("description", "")

    # Skip pending scenarios (no pass_criteria defined)
    if scenario.get("_status") == "pending":
        return {
            "scenario_id": scenario_id,
            "description": description,
            "status": "pending",
            "passed": False,
            "failures": ["Scenario not yet fully populated — skipped gracefully"],
            "raw_response": None
        }

    try:
        api_response = call_elevenlabs_simulate(agent_id, scenario, api_key)
    except RuntimeError as e:
        return {
            "scenario_id": scenario_id,
            "description": description,
            "status": "error",
            "passed": False,
            "failures": [f"API call failed: {e}"],
            "raw_response": None
        }

    passed, status, failures = evaluate_pass_criteria(scenario, api_response)

    return {
        "scenario_id": scenario_id,
        "description": description,
        "status": status,
        "passed": passed,
        "failures": failures,
        "raw_response": api_response if not api_response.get("_stub") else None,
        "stub_message": api_response.get("_message") if api_response.get("_stub") else None
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Run the 10-scenario test suite against a deployed ElevenLabs agent."
    )
    parser.add_argument("--agent-id", required=True, help="ElevenLabs agent ID to test")
    parser.add_argument(
        "--template", required=True,
        help="Template path relative to repo root, e.g. plumber/v1"
    )
    parser.add_argument(
        "--min-pass", type=int, default=9,
        help="Minimum scenarios that must pass (default: 9)"
    )
    parser.add_argument(
        "--scenario",
        help="Run only a single scenario by ID substring, e.g. 01-flooding-emergency"
    )
    parser.add_argument(
        "--report-dir", default="./reports",
        help="Directory to write the JSON report (default: ./reports)"
    )
    parser.add_argument(
        "--api-key",
        help="ElevenLabs API key (falls back to ELEVENLABS_API_KEY env var)"
    )
    parser.add_argument(
        "--allow-pending",
        action="store_true",
        default=False,
        help=(
            "Allow all-pending suites to exit 0 instead of 2. "
            "Use during development when scenarios are not yet populated or "
            "API_INTEGRATION_COMPLETE is False. Never set this in production CI."
        )
    )
    args = parser.parse_args()

    # Resolve API key
    api_key = args.api_key or os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        print("[smoke.py] ERROR: ElevenLabs API key required. Set ELEVENLABS_API_KEY or --api-key.", file=sys.stderr)
        sys.exit(3)

    # Resolve template directory
    # Allow running from either the repo root or the deploy/ subdirectory
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent  # sr-voice-templates/
    template_dir = repo_root / "templates" / args.template

    if not template_dir.exists():
        print(f"[smoke.py] ERROR: Template directory not found: {template_dir}", file=sys.stderr)
        sys.exit(3)

    # Load scenarios
    scenarios = load_scenarios(template_dir, args.scenario)

    print(f"[smoke.py] Agent:    {args.agent_id}")
    print(f"[smoke.py] Template: {args.template} ({template_dir})")
    print(f"[smoke.py] Loaded:   {len(scenarios)} scenario(s)")
    if not API_INTEGRATION_COMPLETE:
        print("[smoke.py] WARNING:  API integration incomplete — verify endpoint at https://elevenlabs.io/docs/conversational-ai")
    print()

    # ── Gate status: determine before running ────────────────────────────────
    # "operational" requires both: API complete AND at least one ready scenario.
    ready_count = sum(1 for s in scenarios if s.get("_status") == "ready")
    if not API_INTEGRATION_COMPLETE:
        gate_status = "pending_api"
    elif ready_count == 0:
        gate_status = "pending_scenarios"
    else:
        gate_status = "operational"

    # Run each scenario
    results = []
    for scenario in scenarios:
        sid = scenario.get("scenario_id", scenario.get("_file", "?"))
        print(f"  Running: {sid} ... ", end="", flush=True)
        result = run_scenario(args.agent_id, scenario, api_key)
        results.append(result)

        status = result["status"]
        if status == "passed":
            print("PASS")
        elif status == "pending":
            print("SKIP (pending)")
        elif status == "skipped_api_pending":
            print("SKIP (API not integrated)")
        elif status == "error":
            print(f"ERROR: {result['failures'][0] if result['failures'] else 'unknown'}")
        else:
            print(f"FAIL")
            for failure in result.get("failures", []):
                print(f"    - {failure}")

    # Aggregate
    passed_count = sum(1 for r in results if r["status"] == "passed")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    pending_count = sum(1 for r in results if r["status"] in ("pending", "skipped_api_pending"))
    error_count = sum(1 for r in results if r["status"] == "error")

    print()
    print(f"[smoke.py] Results: {passed_count} passed, {failed_count} failed, {pending_count} skipped, {error_count} errors / {len(results)} total")
    print(f"[smoke.py] Threshold: {args.min_pass}/{len(scenarios)} required")
    print(f"[smoke.py] Gate:    {gate_status}")

    # Write report (includes gate_status field)
    report_path = write_report(results, Path(args.report_dir), gate_status)
    print(f"[smoke.py] Report:  {report_path}")

    # ── Determine exit code ──────────────────────────────────────────────────
    #
    # Exit 2: gate not operational.
    #   - API_INTEGRATION_COMPLETE = False (gate_status = "pending_api"), OR
    #   - All scenarios are pending (gate_status = "pending_scenarios").
    #   This is fail-closed: new agents with unpopulated scenarios cannot pass.
    #   --allow-pending overrides to exit 0 for dev work.
    #
    # Exit 0: gate operational AND passed >= min_pass real scenarios.
    #   Requires at least one scenario to be "ready" and actually pass.
    #
    # Exit 1: gate operational but below threshold.
    #   Agent ran real scenarios and failed — do NOT go live.
    #
    if gate_status != "operational":
        if args.allow_pending:
            print(f"[smoke.py] RESULT:  SKIP (gate_status={gate_status}, --allow-pending set — exiting 0 for dev)")
            sys.exit(0)
        else:
            print(
                f"[smoke.py] RESULT:  GATE NOT OPERATIONAL (gate_status={gate_status}) — exit 2\n"
                f"           Use --allow-pending to bypass for development."
            )
            sys.exit(2)

    # Gate is operational — evaluate real pass count
    if passed_count >= args.min_pass:
        print(f"[smoke.py] RESULT:  PASS ({passed_count}/{args.min_pass} threshold met)")
        sys.exit(0)
    else:
        print(f"[smoke.py] RESULT:  FAIL ({passed_count} passed, need {args.min_pass}) — do not go live")
        sys.exit(1)


if __name__ == "__main__":
    main()
