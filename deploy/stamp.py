#!/usr/bin/env python3
"""
stamp.py — Compose a per-client voice agent from template + intake data and deploy to ElevenLabs.

PURPOSE
-------
stamp.py is the primary onboarding script for the SR Voice platform. Given a vertical template
(e.g. plumber/v1) and a completed intake form (JSON), it:

  1. Loads the template's workflow.yaml to determine which prompt fragments to assemble
  2. Renders all {{placeholder}} values using the intake form data
  3. Uploads the assembled KB files to ElevenLabs as a knowledge base
  4. Creates or updates the ElevenLabs agent with:
       - Assembled system prompt (concatenated fragments + prompt files)
       - First message from intake form
       - Voice ID from intake form
       - Tool schemas (webhook URLs rendered with client slug + base URL)
       - Reference to the uploaded knowledge base
  5. Writes the ElevenLabs agent_id back into the intake form file
  6. Runs smoke.py against the new agent to verify it passes the test suite

USAGE
-----
  python deploy/stamp.py \\
    --template plumber/v1 \\
    --intake path/to/my-client-intake.json \\
    --client-slug my-client-slug \\
    [--dry-run]       # Render everything but do NOT call ElevenLabs API
    [--skip-smoke]    # Deploy but skip the post-deploy test suite
    [--min-pass 9]    # Minimum scenarios that must pass (default: 9)

ENVIRONMENT VARIABLES
---------------------
  ELEVENLABS_API_KEY   — Required. Your ElevenLabs API key.
  ELEVENLABS_TOOL_SECRET — Optional. Shared secret for webhook tool auth.

IMPLEMENTATION STATUS
---------------------
This is a STUB. The docstring and argument structure are complete.
Full implementation is wired in Task H (Phase 3).

The following functions are defined as stubs with their contracts:
  - load_intake(path) -> dict
  - load_workflow(template_dir) -> dict
  - render_template(text, intake) -> str
  - assemble_system_prompt(workflow, template_dir, intake) -> str
  - upload_knowledge_base(kb_files, intake) -> str  (returns kb_id)
  - render_tool_schemas(tools_dir, intake) -> list[dict]
  - deploy_agent(intake, system_prompt, kb_id, tool_configs) -> str  (returns agent_id)
  - run_smoke(agent_id, template_dir, min_pass) -> bool

EXIT CODES
----------
  0 — Success: agent deployed, smoke tests passed
  1 — Smoke test failure: agent deployed but did not pass minimum scenarios
  2 — Deployment error: ElevenLabs API call failed
  3 — Configuration error: intake form missing required fields
"""

import argparse
import json
import sys
from pathlib import Path


def load_intake(path: str) -> dict:
    """
    Load and validate the client intake form JSON.

    Args:
        path: Absolute or relative path to the intake form JSON file.

    Returns:
        Parsed intake dict.

    Raises:
        SystemExit(3) if required fields are missing or JSON is malformed.
    """
    # STUB — Task H implements validation against intake-form.json $schema
    raise NotImplementedError("stamp.py: load_intake() not yet implemented — wired in Task H")


def load_workflow(template_dir: Path) -> dict:
    """
    Load and parse the template's workflow.yaml.

    Args:
        template_dir: Path to the vertical template directory (e.g. templates/plumber/v1/)

    Returns:
        Parsed workflow dict containing llm_nodes, tools, fragment order, etc.
    """
    # STUB — Task H implements YAML parsing
    raise NotImplementedError("stamp.py: load_workflow() not yet implemented — wired in Task H")


def render_template(text: str, intake: dict) -> str:
    """
    Replace all {{placeholder}} markers in text with values from intake.

    Args:
        text: Raw template text containing {{placeholder}} markers.
        intake: Intake form dict.

    Returns:
        Rendered text with all placeholders substituted.

    Raises:
        ValueError if any {{placeholder}} in text has no matching key in intake.
    """
    # STUB — Task H implements regex-based substitution with missing-key error reporting
    raise NotImplementedError("stamp.py: render_template() not yet implemented — wired in Task H")


def assemble_system_prompt(workflow: dict, template_dir: Path, intake: dict) -> str:
    """
    Concatenate all fragment and prompt files in the order defined by workflow.yaml
    for the 'triage' node (which is the agent's primary system prompt).

    Args:
        workflow: Parsed workflow.yaml dict.
        template_dir: Root path of the template (for resolving relative file paths).
        intake: Rendered intake dict.

    Returns:
        Single assembled system prompt string, ready for ElevenLabs agent config.
    """
    # STUB — Task H implements fragment concatenation with placeholder rendering
    raise NotImplementedError("stamp.py: assemble_system_prompt() not yet implemented — wired in Task H")


def upload_knowledge_base(kb_files: list, intake: dict) -> str:
    """
    Upload rendered KB files to ElevenLabs as a knowledge base for this client.

    Args:
        kb_files: List of rendered KB file contents (strings).
        intake: Intake dict (provides client_slug for naming).

    Returns:
        ElevenLabs knowledge_base_id string.
    """
    # STUB — Task H implements via POST /v1/convai/knowledge-base
    raise NotImplementedError("stamp.py: upload_knowledge_base() not yet implemented — wired in Task H")


def render_tool_schemas(tools_dir: Path, intake: dict) -> list:
    """
    Load tool JSON schemas from tools/ directory, render {{placeholder}} values,
    and return the list ready for ElevenLabs tool provisioning.

    Args:
        tools_dir: Path to the tools/ directory.
        intake: Intake dict providing webhook_base_url, client_slug, tool_secret.

    Returns:
        List of rendered tool config dicts.
    """
    # STUB — Task H implements JSON loading + placeholder substitution
    raise NotImplementedError("stamp.py: render_tool_schemas() not yet implemented — wired in Task H")


def deploy_agent(intake: dict, system_prompt: str, kb_id: str, tool_configs: list) -> str:
    """
    Create or update the ElevenLabs agent via the ConvAI API.
    Idempotent: if intake contains an existing elevenlabs_agent_id, patches in place.

    Args:
        intake: Full intake dict (provides voice_id, first_message, agent_name, etc.)
        system_prompt: Assembled system prompt string.
        kb_id: ElevenLabs knowledge base ID from upload_knowledge_base().
        tool_configs: List of rendered tool config dicts from render_tool_schemas().

    Returns:
        ElevenLabs agent_id string.
    """
    # STUB — Task H implements via POST/PATCH /v1/convai/agents
    raise NotImplementedError("stamp.py: deploy_agent() not yet implemented — wired in Task H")


def run_smoke(agent_id: str, template_dir: Path, min_pass: int = 9) -> bool:
    """
    Invoke smoke.py against the newly deployed agent.

    Args:
        agent_id: ElevenLabs agent ID to test.
        template_dir: Template directory (to locate tests/simulation/).
        min_pass: Minimum number of scenarios that must pass (default 9).

    Returns:
        True if smoke tests pass, False otherwise.
    """
    # STUB — Task H implements subprocess call to smoke.py
    raise NotImplementedError("stamp.py: run_smoke() not yet implemented — wired in Task H")


def main():
    parser = argparse.ArgumentParser(
        description="Compose a per-client voice agent from template + intake data and deploy to ElevenLabs."
    )
    parser.add_argument("--template", required=True, help="Template path relative to repo root, e.g. plumber/v1")
    parser.add_argument("--intake", required=True, help="Path to the completed intake form JSON")
    parser.add_argument("--client-slug", required=True, help="Client slug (must match intake form)")
    parser.add_argument("--dry-run", action="store_true", help="Render everything but do not call ElevenLabs API")
    parser.add_argument("--skip-smoke", action="store_true", help="Deploy without running post-deploy tests")
    parser.add_argument("--min-pass", type=int, default=9, help="Minimum scenarios that must pass smoke test (default: 9)")
    args = parser.parse_args()

    print(f"[stamp.py] STUB — implementation pending Task H")
    print(f"  template:    {args.template}")
    print(f"  intake:      {args.intake}")
    print(f"  client-slug: {args.client_slug}")
    print(f"  dry-run:     {args.dry_run}")
    print(f"  skip-smoke:  {args.skip_smoke}")
    print(f"  min-pass:    {args.min_pass}")
    sys.exit(0)


if __name__ == "__main__":
    main()
