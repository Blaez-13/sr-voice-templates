#!/usr/bin/env python3
"""
stamp.py — Compose a per-client voice agent from template + intake data and deploy to ElevenLabs.

PURPOSE
-------
stamp.py is the primary onboarding script for the SR Voice platform. Given a vertical template
(e.g. plumber/v1) and a completed intake form (JSON), it:

  1. Loads the template's workflow.yaml to determine which prompt fragments to assemble
  2. Validates the intake JSON against the template's intake-form.json schema
  3. Renders all {{placeholder}} values using the intake form data
  4. Composes all per-node prompts and concatenates them into ONE system prompt using
     ## section headers (e.g. ## Triage, ## Emergency, ## Booking, etc.)
     Architecture decision: ONE-AGENT-PER-CLIENT for MVP. Multi-agent Workflow setup
     with independent per-node agents is deferred to v2 (Decision H, 2026-04-16).
  5. Renders KB content (substitutes placeholders from intake)
  6. POSTs to the voice-bot-url /api/clients/<slug>/elevenlabs/sync-from-template with
     payload { template, intake }
  7. Gets back the agent_id from the response
  8. Runs smoke.py with that agent_id
  9. Prints summary and exits with smoke.py's exit code

USAGE
-----
  python deploy/stamp.py \\
    --template plumber/v1 \\
    --intake path/to/my-client-intake.json \\
    --client-slug my-client-slug \\
    [--api-key <elevenlabs_api_key>]    # Falls back to ELEVENLABS_API_KEY env var
    [--voice-bot-url http://localhost:8080]  # Default: http://localhost:8080
    [--dry-run]                         # Render everything but do NOT call any API
    [--skip-smoke]                      # Deploy but skip the post-deploy test suite
    [--min-pass 9]                      # Minimum scenarios that must pass (default: 9)

ENVIRONMENT VARIABLES
---------------------
  ELEVENLABS_API_KEY   — Required unless --api-key is provided.
  VOICE_BOT_URL        — Override default voice-bot service URL. Also --voice-bot-url flag.

ARCHITECTURE NOTE (ONE-AGENT-PER-CLIENT)
-----------------------------------------
The plumber template produces per-node prompts (triage, emergency, booking, support, billing).
ElevenLabs Workflows architecture supports independent Subagent Nodes with per-node prompts,
but that requires setting up a Workflow graph with multiple agents — a v2 concern.

For MVP, stamp.py concatenates all node prompts into a SINGLE system prompt using
## section headers. This aligns with ElevenLabs' simpler single-agent architecture and
makes testing straightforward. The concatenated format is:

  ## Triage
  <triage node prompt>

  ## Emergency
  <emergency node prompt>

  ...

The triage node is always first. A skilled agent reads section context and routes
accordingly. Multi-agent Workflow decomposition is flagged for Phase 4 review.

EXIT CODES
----------
  0 — Success: agent deployed and smoke tests passed (or --skip-smoke used)
  1 — Smoke test failure: agent deployed but did not pass minimum scenarios
  2 — Deployment error: voice-bot API call or ElevenLabs call failed
  3 — Configuration error: intake form missing required fields, template not found, etc.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------
try:
    import urllib.request
    import urllib.error
    _HAS_URLLIB = True
except ImportError:
    _HAS_URLLIB = False

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# ---------------------------------------------------------------------------
# Repo paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent  # sr-voice-templates/
TEMPLATES_DIR = REPO_ROOT / "templates"
FRAGMENTS_DIR = REPO_ROOT / "fragments"


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------
def load_yaml_file(path: Path) -> dict:
    """Load a YAML file. Uses PyYAML if available, else a minimal fallback."""
    text = path.read_text(encoding="utf-8")
    if _HAS_YAML:
        docs = list(yaml.safe_load_all(text))
        return docs[0] if docs else {}
    # Minimal fallback — only handles top-level scalars
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
# Intake loading and validation
# ---------------------------------------------------------------------------
def load_intake(intake_path: str) -> dict:
    """
    Load and perform basic validation of the client intake form JSON.

    Validates required fields are present against the template's intake-form.json
    schema. Does not validate field formats — that is ElevenLabs' responsibility.

    Args:
        intake_path: Path to the intake form JSON file.

    Returns:
        Parsed intake dict.

    Raises:
        SystemExit(3) if required fields are missing or JSON is malformed.
    """
    p = Path(intake_path)
    if not p.exists():
        print(f"[stamp.py] ERROR: intake file not found: {p}", file=sys.stderr)
        sys.exit(3)
    try:
        intake = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[stamp.py] ERROR: intake JSON parse error: {e}", file=sys.stderr)
        sys.exit(3)
    if not isinstance(intake, dict):
        print("[stamp.py] ERROR: intake must be a JSON object", file=sys.stderr)
        sys.exit(3)
    return intake


def validate_intake_against_schema(intake: dict, template_dir: Path) -> list:
    """
    Check that all required fields from intake-form.json are present in the intake.
    Returns a list of missing field names (empty if all present).
    """
    schema_path = template_dir / "intake-form.json"
    if not schema_path.exists():
        return []  # No schema to validate against — skip

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []  # Malformed schema — skip rather than crash

    required = schema.get("required", [])
    missing = [f for f in required if f not in intake or intake[f] in (None, "", [])]
    return missing


# ---------------------------------------------------------------------------
# Workflow loading
# ---------------------------------------------------------------------------
def load_workflow(template_dir: Path) -> dict:
    """
    Load and parse the template's workflow.yaml.
    Uses a simple line-based parser to avoid heavy YAML dependencies.
    Falls back to PyYAML if available.

    Returns a dict with at minimum:
      llm_nodes: { node_name: { prompt_files: [...], model, temperature } }
      knowledge_base_files: [...]
    """
    wf_path = template_dir / "workflow.yaml"
    if not wf_path.exists():
        print(f"[stamp.py] ERROR: workflow.yaml not found in {template_dir}", file=sys.stderr)
        sys.exit(3)

    if _HAS_YAML:
        return load_yaml_file(wf_path)

    # Line-based fallback (mirrors template-loader.js parseWorkflowYaml logic)
    text = wf_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    result = {"llm_nodes": {}, "knowledge_base_files": [], "tts": {}, "tools": []}
    current_node = None
    current_section = None
    in_prompt_files = False
    in_tools = False
    in_kb = False

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#") or line.strip() == "---":
            continue

        if re.match(r"^knowledge_base_files:", line):
            current_section = "kb"; in_prompt_files = False; in_tools = False; in_kb = True; current_node = None
        elif re.match(r"^tools:", line):
            current_section = "tools"; in_prompt_files = False; in_tools = True; in_kb = False; current_node = None
        elif re.match(r"^tts:", line):
            current_section = "tts"; in_prompt_files = False; in_tools = False; in_kb = False; current_node = None
        elif re.match(r"^llm_nodes:", line):
            current_section = "llm_nodes"; in_prompt_files = False; in_tools = False; in_kb = False
        elif current_section == "tts" and re.match(r"^\s+(model|voice_id):", line):
            m = re.match(r"^\s+(model|voice_id):\s*(.+)$", line)
            if m:
                result["tts"][m.group(1)] = m.group(2).strip().strip('"\'')
        elif current_section == "llm_nodes" and re.match(r"^  \w+:", line):
            current_node = line.strip().rstrip(":")
            result["llm_nodes"][current_node] = {"prompt_files": []}
            in_prompt_files = False
        elif current_node and re.match(r"^\s+prompt_files:", line):
            in_prompt_files = True
        elif current_node and not in_prompt_files and re.match(r"^\s+(model|temperature|reasoning_effort):\s", line):
            m = re.match(r"^\s+(model|temperature|reasoning_effort):\s*(.+)$", line)
            if m:
                val = m.group(2).strip()
                result["llm_nodes"][current_node][m.group(1)] = float(val) if re.match(r"^\d+\.\d+$", val) else val
        elif current_node and in_prompt_files and re.match(r"^\s+-\s", line):
            item = re.sub(r"^\s+-\s+", "", line).split("#")[0].strip()
            if item:
                result["llm_nodes"][current_node]["prompt_files"].append(item)
        elif in_tools and re.match(r"^\s+-\s", line):
            item = re.sub(r"^\s+-\s+", "", line).split("#")[0].strip()
            if item:
                result["tools"].append(item)
        elif in_kb and re.match(r"^\s+-\s", line):
            item = re.sub(r"^\s+-\s+", "", line).split("#")[0].strip()
            if item:
                result["knowledge_base_files"].append(item)
        elif current_node and re.match(r"^\s{4}\w+:", line) and not re.match(r"^\s+-", line):
            in_prompt_files = False

    return result


# ---------------------------------------------------------------------------
# Placeholder rendering
# ---------------------------------------------------------------------------
def render_template(text: str, intake: dict) -> str:
    """
    Replace {{placeholder}} markers in text with values from intake.
    Unknown placeholders are left as-is (some resolve at runtime).

    Raises:
        Nothing — missing keys are silently preserved so callers can
        decide whether to warn or error.
    """
    def replacer(match):
        key = match.group(1)
        if key in intake:
            val = intake[key]
            if isinstance(val, list):
                return ", ".join(str(v) for v in val)
            return str(val)
        return match.group(0)  # leave unresolved placeholder intact

    return re.sub(r"\{\{(\w+)\}\}", replacer, text)


def check_unresolved(text: str) -> list:
    """Return a list of any {{placeholder}} markers remaining in text."""
    return re.findall(r"\{\{(\w+)\}\}", text)


# ---------------------------------------------------------------------------
# Prompt assembly — ONE-AGENT-PER-CLIENT strategy
# ---------------------------------------------------------------------------
def assemble_system_prompt(workflow: dict, intake: dict) -> str:
    """
    Concatenate all LLM node prompts into a single system prompt using
    ## section headers. Node order: triage first, then alphabetical.

    This is the ONE-AGENT-PER-CLIENT strategy for MVP. The ElevenLabs agent
    receives a single system prompt containing all node instructions separated
    by ## headers. A well-prompted agent routes internally based on context.

    Args:
        workflow: Parsed workflow.yaml dict.
        intake:   Intake form dict for placeholder substitution.

    Returns:
        Assembled system prompt string ready for ElevenLabs.
    """
    nodes = workflow.get("llm_nodes", {})
    if not nodes:
        return ""

    # Node order: triage first, then alphabetical
    node_order = []
    if "triage" in nodes:
        node_order.append("triage")
    node_order.extend(sorted(k for k in nodes.keys() if k != "triage"))

    sections = []
    for node_name in node_order:
        node_config = nodes[node_name]
        prompt_files = node_config.get("prompt_files", [])
        parts = []
        for rel_path in prompt_files:
            abs_path = REPO_ROOT / rel_path
            if not abs_path.exists():
                print(f"[stamp.py] WARNING: prompt file not found: {abs_path} (skipping)", file=sys.stderr)
                continue
            content = abs_path.read_text(encoding="utf-8")
            rendered = render_template(content, intake)
            parts.append(rendered)
        node_prompt = "\n\n".join(parts)
        # Add section header
        header = f"## {node_name.capitalize()}"
        sections.append(f"{header}\n\n{node_prompt}")

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# KB rendering
# ---------------------------------------------------------------------------
def render_kb(template_dir: Path, intake: dict) -> list:
    """
    Load and render all KB markdown files with intake placeholders.

    Returns:
        List of { name: str, content: str } dicts.
    """
    kb_dir = template_dir / "kb"
    if not kb_dir.exists():
        return []

    docs = []
    for kb_file in sorted(kb_dir.glob("*.md")):
        content = kb_file.read_text(encoding="utf-8")
        rendered = render_template(content, intake)
        docs.append({"name": kb_file.stem, "content": rendered})
    return docs


# ---------------------------------------------------------------------------
# Voice-bot API call: sync-from-template
# ---------------------------------------------------------------------------
def call_sync_from_template(voice_bot_url: str, client_slug: str, template_name: str, intake: dict) -> dict:
    """
    POST to the voice-bot's sync-from-template endpoint.

    Endpoint: POST <voice_bot_url>/api/clients/<slug>/elevenlabs/sync-from-template
    Body: { template: str, intake: dict }

    Returns:
        Response JSON dict (should include agent_id or agent.agent_id).

    Raises:
        RuntimeError on HTTP or connection error.
    """
    url = f"{voice_bot_url.rstrip('/')}/api/clients/{client_slug}/elevenlabs/sync-from-template"
    payload = json.dumps({"template": template_name, "intake": intake}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"voice-bot API HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"voice-bot API connection error: {e.reason}")


# ---------------------------------------------------------------------------
# Smoke test invocation
# ---------------------------------------------------------------------------
def run_smoke(agent_id: str, template: str, min_pass: int, api_key: str, report_dir: str) -> int:
    """
    Invoke smoke.py as a subprocess against the deployed agent.

    Returns smoke.py's exit code (0 = pass, 1 = fail, 2+ = error).
    """
    smoke_py = SCRIPT_DIR / "smoke.py"
    cmd = [
        sys.executable, str(smoke_py),
        "--agent-id", agent_id,
        "--template", template,
        "--min-pass", str(min_pass),
        "--report-dir", report_dir,
    ]
    if api_key:
        cmd.extend(["--api-key", api_key])

    result = subprocess.run(cmd)
    return result.returncode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Compose a per-client voice agent from template + intake data and deploy to ElevenLabs."
    )
    parser.add_argument("--template", required=True, help="Template path, e.g. plumber/v1")
    parser.add_argument("--intake", required=True, help="Path to the completed intake form JSON")
    parser.add_argument("--client-slug", required=True, help="Client slug (must match intake client_slug)")
    parser.add_argument(
        "--api-key",
        help="ElevenLabs API key (falls back to ELEVENLABS_API_KEY env var)"
    )
    parser.add_argument(
        "--voice-bot-url",
        default=os.environ.get("VOICE_BOT_URL", "http://localhost:8080"),
        help="Voice-bot service base URL (default: http://localhost:8080)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Render everything but do not call any API")
    parser.add_argument("--skip-smoke", action="store_true", help="Deploy without running post-deploy tests")
    parser.add_argument("--min-pass", type=int, default=9, help="Minimum scenarios that must pass smoke test (default: 9)")
    parser.add_argument("--report-dir", default="./reports", help="Directory for smoke test report (default: ./reports)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("ELEVENLABS_API_KEY", "")

    # 1. Locate template
    template_dir = TEMPLATES_DIR / args.template
    if not template_dir.exists():
        print(f"[stamp.py] ERROR: Template not found: {template_dir}", file=sys.stderr)
        sys.exit(3)

    print(f"[stamp.py] Template:     {args.template} ({template_dir})")
    print(f"[stamp.py] Client slug:  {args.client_slug}")
    print(f"[stamp.py] Intake:       {args.intake}")
    if args.dry_run:
        print("[stamp.py] Mode:         DRY RUN — no API calls will be made")
    print()

    # 2. Load intake
    intake = load_intake(args.intake)

    # Inject client_slug if not present (CLI arg takes precedence)
    if "client_slug" not in intake:
        intake["client_slug"] = args.client_slug
    elif intake["client_slug"] != args.client_slug:
        print(
            f"[stamp.py] WARNING: --client-slug '{args.client_slug}' differs from intake client_slug '{intake['client_slug']}'. "
            "Using --client-slug.",
            file=sys.stderr
        )
        intake["client_slug"] = args.client_slug

    # 3. Validate required fields
    missing = validate_intake_against_schema(intake, template_dir)
    if missing:
        print(f"[stamp.py] ERROR: Intake missing required fields: {', '.join(missing)}", file=sys.stderr)
        sys.exit(3)
    print(f"[stamp.py] Intake validation: OK ({len(intake)} fields)")

    # 4. Load workflow
    workflow = load_workflow(template_dir)
    node_names = list(workflow.get("llm_nodes", {}).keys())
    print(f"[stamp.py] Nodes:        {', '.join(node_names)}")

    # 5. Compose system prompt (all nodes concatenated under ## headers)
    print("[stamp.py] Composing system prompt (ONE-AGENT strategy) ...")
    system_prompt = assemble_system_prompt(workflow, intake)
    unresolved = check_unresolved(system_prompt)
    if unresolved:
        print(f"[stamp.py] WARNING: {len(unresolved)} unresolved placeholder(s) in system prompt: {unresolved[:5]}", file=sys.stderr)
    print(f"[stamp.py] System prompt: {len(system_prompt)} chars, {len(unresolved)} unresolved placeholders")

    # 6. Render KB
    print("[stamp.py] Rendering knowledge base ...")
    kb_docs = render_kb(template_dir, intake)
    print(f"[stamp.py] KB:           {len(kb_docs)} document(s)")

    if args.dry_run:
        print()
        print("[stamp.py] DRY RUN complete. System prompt preview (first 500 chars):")
        print("-" * 60)
        print(system_prompt[:500])
        print("-" * 60)
        if kb_docs:
            print(f"\nKB documents: {[d['name'] for d in kb_docs]}")
        sys.exit(0)

    # 7. POST to voice-bot sync-from-template
    print(f"[stamp.py] Pushing to voice-bot: {args.voice_bot_url} ...")
    try:
        response = call_sync_from_template(
            args.voice_bot_url,
            args.client_slug,
            args.template,
            intake
        )
    except RuntimeError as e:
        print(f"[stamp.py] ERROR: voice-bot API call failed: {e}", file=sys.stderr)
        sys.exit(2)

    # Extract agent_id from response
    agent_id = (
        response.get("agent_id")
        or (response.get("agent") or {}).get("agent_id")
        or response.get("elevenlabs_agent_id")
    )
    if not agent_id:
        print(f"[stamp.py] ERROR: no agent_id in voice-bot response. Response: {json.dumps(response)[:400]}", file=sys.stderr)
        sys.exit(2)

    print(f"[stamp.py] Agent deployed: {agent_id}")
    print(f"[stamp.py] Nodes composed: {response.get('nodes_composed', node_names)}")
    print(f"[stamp.py] KB docs updated: {response.get('kb_docs_updated', 0)}")
    print(f"[stamp.py] Last synced: {response.get('last_synced_at', 'n/a')}")

    # 8. Run smoke tests
    if args.skip_smoke:
        print()
        print("[stamp.py] Smoke tests: SKIPPED (--skip-smoke)")
        print("[stamp.py] SUCCESS: Agent deployed. Run smoke.py manually to verify before go-live.")
        sys.exit(0)

    if not api_key:
        print("[stamp.py] WARNING: ELEVENLABS_API_KEY not set — skipping smoke tests", file=sys.stderr)
        print("[stamp.py] SUCCESS: Agent deployed. Set ELEVENLABS_API_KEY and run smoke.py to verify.")
        sys.exit(0)

    print()
    print(f"[stamp.py] Running smoke tests (min-pass={args.min_pass}) ...")
    smoke_exit = run_smoke(agent_id, args.template, args.min_pass, api_key, args.report_dir)

    print()
    if smoke_exit == 0:
        print(f"[stamp.py] RESULT: PASS — agent {agent_id} is ready for go-live")
    else:
        print(f"[stamp.py] RESULT: FAIL (exit {smoke_exit}) — agent {agent_id} did NOT pass smoke tests. Do NOT go live.")

    sys.exit(smoke_exit)


if __name__ == "__main__":
    main()
