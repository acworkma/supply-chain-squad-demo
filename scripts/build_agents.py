#!/usr/bin/env python3
"""Validate Azure AI Foundry connectivity for the supply closet replenishment demo.

Uses the Microsoft Agent Framework SDK to verify that the Foundry project
endpoint is reachable and the model deployment is accessible.  Actual agent
definitions are created at runtime by the orchestrator.

Usage:
    python scripts/build_agents.py

Requires env vars (one of):
    FOUNDRY_PROJECT_ENDPOINT   — Azure AI Foundry project endpoint (preferred)
    PROJECT_ENDPOINT           — Legacy endpoint name (fallback)

Optional:
    FOUNDRY_MODEL_DEPLOYMENT_NAME — Model deployment name (preferred)
    MODEL_DEPLOYMENT_NAME         — Legacy model name (fallback, default: gpt-4.1)
"""

import asyncio
import os
import sys


AGENT_NAMES = [
    "supply-coordinator",
    "supply-scanner",
    "catalog-sourcer",
    "order-manager",
    "compliance-gate",
]

PROMPTS_DIR = (
    __import__("pathlib").Path(__file__).resolve().parent.parent
    / "src" / "api" / "app" / "agents" / "prompts"
)


async def validate() -> None:
    """Verify Foundry endpoint and model deployment are accessible."""
    from agent_framework.foundry import FoundryChatClient
    from azure.identity.aio import DefaultAzureCredential

    endpoint = (
        os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
        or os.environ.get("PROJECT_ENDPOINT", "").strip()
    )
    if not endpoint:
        # Fallback: parse legacy connection string
        conn_str = os.environ.get("PROJECT_CONNECTION_STRING", "").strip()
        if conn_str:
            parts = conn_str.split(";")
            if len(parts) == 4:
                host, _sub_id, _rg, project = parts
                endpoint = f"https://{host}/api/projects/{project}"
            else:
                print(
                    f"ERROR: Invalid PROJECT_CONNECTION_STRING format "
                    f"(expected 4 parts, got {len(parts)}).",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            print(
                "ERROR: No Foundry endpoint configured. Set FOUNDRY_PROJECT_ENDPOINT "
                "or PROJECT_ENDPOINT.",
                file=sys.stderr,
            )
            sys.exit(1)

    model = (
        os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "").strip()
        or os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4.1").strip()
    )

    print(f"Validating Foundry connection...")
    print(f"  Endpoint: {endpoint[:60]}...")
    print(f"  Model:    {model}")

    credential = DefaultAzureCredential()
    try:
        client = FoundryChatClient(
            project_endpoint=endpoint,
            model=model,
            credential=credential,
        )
        from agent_framework import Message
        response = await client.get_response([
            Message(role="system", contents=["You are a test agent. Reply with OK."]),
            Message(role="user", contents=["ping"]),
        ])
        print(f"  ✅ Agent Framework connection validated")
        print(f"  ✅ Model deployment '{model}' accessible")
    except Exception as exc:
        print(f"  ✗ Validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        await credential.close()

    # Verify prompt files exist for all agents
    missing = [n for n in AGENT_NAMES if not (
        PROMPTS_DIR / f"{n}.txt").exists()]
    if missing:
        print(
            f"  ⚠ Missing prompt files: {', '.join(missing)}", file=sys.stderr)
    else:
        print(f"  ✅ All {len(AGENT_NAMES)} agent prompt files found")

    print("\nValidation complete. Agents will be created at runtime by the orchestrator.")


if __name__ == "__main__":
    asyncio.run(validate())
