#!/usr/bin/env python3
"""Build (create/update) Azure AI Foundry agents for the supply closet replenishment demo.

Uses the v2 Azure AI Projects SDK: creates each agent as a named, versioned
Foundry agent via ``agents.create_version()``.  At runtime the orchestrator
invokes agents by *name* through the Responses API — no opaque IDs needed.

Usage:
    python scripts/build_agents.py

Requires env vars (one of):
    PROJECT_ENDPOINT           — Azure AI Foundry project endpoint (preferred)
    PROJECT_CONNECTION_STRING  — Azure AI Foundry project connection string (fallback)

Optional:
    MODEL_DEPLOYMENT_NAME      — Model deployment to use (default: gpt-4.1)
    AGENT_MODEL_OVERRIDES      — JSON string of per-agent model overrides
                                 Example: '{"supply-scanner":"gpt-5-mini"}'
"""

import json
import os
import sys
from pathlib import Path

AGENT_NAMES = [
    "supply-coordinator",
    "supply-scanner",
    "catalog-sourcer",
    "order-manager",
    "compliance-gate",
]

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "src" / "api" / "app" / "agents" / "prompts"


def _get_project_client():
    """Create an AIProjectClient using endpoint (preferred) or connection string."""
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()

    endpoint = os.environ.get("PROJECT_ENDPOINT", "").strip()
    conn_str = os.environ.get("PROJECT_CONNECTION_STRING", "").strip()

    if endpoint:
        print(f"Using PROJECT_ENDPOINT: {endpoint[:40]}...")
        return AIProjectClient(endpoint=endpoint, credential=credential)
    elif conn_str:
        parts = conn_str.split(";")
        if len(parts) == 4:
            host, sub_id, rg, project = parts
            endpoint = f"https://{host}/api/projects/{project}"
            print(f"Using PROJECT_CONNECTION_STRING → endpoint: {endpoint[:60]}...")
            return AIProjectClient(endpoint=endpoint, credential=credential)
        else:
            print(
                f"ERROR: Invalid PROJECT_CONNECTION_STRING format "
                f"(expected 4 parts, got {len(parts)}).",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print(
            "ERROR: Neither PROJECT_ENDPOINT nor PROJECT_CONNECTION_STRING is set.",
            file=sys.stderr,
        )
        sys.exit(1)


def _load_tool_definitions() -> dict[str, list]:
    """Import per-agent FunctionTool lists from the app package."""
    api_src = Path(__file__).resolve().parent.parent / "src" / "api"
    if str(api_src) not in sys.path:
        sys.path.insert(0, str(api_src))

    from app.tools.tool_schemas import AGENT_TOOLS_V2
    return AGENT_TOOLS_V2


def main() -> None:
    from azure.ai.projects.models import PromptAgentDefinition

    model_deployment = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4.1")

    try:
        model_overrides: dict[str, str] = json.loads(
            os.environ.get("AGENT_MODEL_OVERRIDES", "{}")
        )
    except (json.JSONDecodeError, TypeError):
        model_overrides = {}

    project_client = _get_project_client()
    agents_ops = project_client.agents

    tool_defs = _load_tool_definitions()

    for agent_name in AGENT_NAMES:
        prompt_file = PROMPTS_DIR / f"{agent_name}.txt"
        if prompt_file.exists():
            system_prompt = prompt_file.read_text().strip()
        else:
            print(f"  Warning: No prompt file for {agent_name}, using default", file=sys.stderr)
            system_prompt = f"You are the {agent_name} agent for the hospital supply-closet replenishment system."

        tools = tool_defs.get(agent_name, [])

        agent_model = model_overrides.get(agent_name) or model_deployment
        definition = PromptAgentDefinition(
            model=agent_model,
            instructions=system_prompt,
            tools=tools,
            temperature=0.3,
        )

        print(f"  Creating/updating agent version: {agent_name}")
        try:
            version = agents_ops.create_version(
                agent_name=agent_name,
                definition=definition,
                description=f"Supply closet replenishment {agent_name} agent",
            )
            print(f"  ✓ {agent_name} → version {version.id}")
        except Exception as exc:
            print(f"  ✗ Error for {agent_name}: {exc}", file=sys.stderr)

    print("\nAll agents published. Invoke by name via the Responses API.")


if __name__ == "__main__":
    main()
