#!/usr/bin/env python3
"""Register persistent Foundry prompt agents for the supply-closet demo.

Runs once during ``azd up`` postprovision. Creates (or updates) each of the
five prompt agents so they appear in the Microsoft Foundry portal.

Agents registered:
    * supply-coordinator
    * supply-scanner
    * catalog-sourcer
    * order-manager
    * compliance-gate

Usage:
    python scripts/build_agents.py

Required env vars (one of):
    FOUNDRY_PROJECT_ENDPOINT   — Foundry project endpoint (preferred)
    PROJECT_ENDPOINT           — Legacy endpoint name

Optional:
    FOUNDRY_MODEL_DEPLOYMENT_NAME — Model deployment (preferred)
    MODEL_DEPLOYMENT_NAME         — Legacy model name (fallback: gpt-4.1)
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
import uuid
from pathlib import Path

# Make src/api importable so we can reuse the registry module.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src" / "api"))


def _resolve_endpoint() -> str:
    endpoint = (
        os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
        or os.environ.get("PROJECT_ENDPOINT", "").strip()
    )
    if endpoint:
        return endpoint
    conn_str = os.environ.get("PROJECT_CONNECTION_STRING", "").strip()
    if conn_str:
        parts = conn_str.split(";")
        if len(parts) == 4:
            host, _sub_id, _rg, project = parts
            return f"https://{host}/api/projects/{project}"
        print(
            f"ERROR: Invalid PROJECT_CONNECTION_STRING (expected 4 parts, got {len(parts)}).",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        "ERROR: No Foundry endpoint configured. Set FOUNDRY_PROJECT_ENDPOINT "
        "or PROJECT_ENDPOINT.",
        file=sys.stderr,
    )
    sys.exit(1)


def _playground_link(endpoint: str, agent_name: str, version: str) -> str | None:
    """Build a Microsoft Foundry portal playground link.

    Returns None if the required azd env values are missing; the table still
    prints agent + version but without a link.
    """
    sub_id = os.environ.get("AZURE_SUBSCRIPTION_ID", "").strip()
    rg = os.environ.get("AZURE_RESOURCE_GROUP", "").strip()
    account = os.environ.get("FOUNDRY_ACCOUNT_NAME", "").strip()
    project = os.environ.get("FOUNDRY_PROJECT_NAME", "").strip()
    if not (sub_id and rg and account and project):
        return None
    try:
        encoded_sub = (
            base64.urlsafe_b64encode(uuid.UUID(sub_id).bytes).rstrip(b"=").decode()
        )
    except ValueError:
        return None
    return (
        f"https://ai.azure.com/nextgen/r/{encoded_sub},{rg},,{account},{project}"
        f"/build/agents/{agent_name}/build?version={version}"
    )


async def main() -> None:
    endpoint = _resolve_endpoint()
    model = (
        os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "").strip()
        or os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4.1").strip()
    )

    print(f"Registering persistent Foundry agents")
    print(f"  Endpoint: {endpoint[:70]}...")
    print(f"  Model:    {model}")
    print()

    # Import lazily so pip install can run before this module resolves its deps.
    from azure.identity.aio import DefaultAzureCredential
    from app.agents.registry import AGENT_NAMES, sync_agents

    credential = DefaultAzureCredential()
    try:
        results = await sync_agents(
            endpoint=endpoint,
            credential=credential,
            model_deployment=model,
        )
    finally:
        await credential.close()

    print("Registration results:")
    print(f"{'AGENT':<22} {'VERSION':<10} {'STATUS':<10}  PROMPT PREVIEW")
    print("-" * 100)
    for reg in results:
        print(
            f"{reg.agent_name:<22} {reg.version:<10} {reg.status:<10}  {reg.prompt_preview}"
        )

    # Playground links (only if azd env vars are populated)
    links_shown = False
    for reg in results:
        link = _playground_link(endpoint, reg.agent_name, reg.version)
        if link:
            if not links_shown:
                print("\nFoundry portal links:")
                links_shown = True
            print(f"  {reg.agent_name}: {link}")

    if len(results) != len(AGENT_NAMES):
        print(
            f"\nERROR: Registered {len(results)} of {len(AGENT_NAMES)} agents.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"\n✅ All {len(results)} agents registered in Foundry.")

    await _bootstrap_evals(endpoint=endpoint, model=model, agent_names=[r.agent_name for r in results])


async def _bootstrap_evals(*, endpoint: str, model: str, agent_names: list[str]) -> None:
    """Launch one Foundry evaluation run per agent against a portal-authored eval template.

    Soft-fails: a broken eval run must never block agent registration success.
    Controlled by env vars:
        FOUNDRY_EVAL_ID           — eval template id (required; skipped if unset)
        FOUNDRY_BOOTSTRAP_EVALS   — set to "false" to opt out
        FOUNDRY_EVAL_SAMPLES      — samples per run (default 15)
        FOUNDRY_EVAL_AGENT_VERSION — agent version to target (default "1")
    """
    # Import lazily so registration still works if evals_runner has a bug.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from evals_runner import (  # type: ignore[import-not-found]
            bootstrap_enabled,
            resolve_eval_id,
            trigger_runs,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"\n⚠️  Skipping eval bootstrap (import failed): {exc}")
        return

    if not bootstrap_enabled():
        print("\nℹ️  Eval bootstrap disabled (FOUNDRY_BOOTSTRAP_EVALS=false).")
        return
    eval_id = resolve_eval_id()
    if not eval_id:
        print(
            "\nℹ️  Skipping eval bootstrap: FOUNDRY_EVAL_ID is not set. "
            "Create an eval template in the Foundry portal and set "
            "FOUNDRY_EVAL_ID=<eval_...> to enable programmatic runs."
        )
        return

    samples = int(os.environ.get("FOUNDRY_EVAL_SAMPLES", "15"))
    agent_version = os.environ.get("FOUNDRY_EVAL_AGENT_VERSION", "1").strip() or "1"

    print(f"\nLaunching Foundry evaluation runs (eval_id={eval_id})")
    print(f"  Samples per run: {samples}")
    print(f"  Agent version:   {agent_version}")

    from azure.identity.aio import DefaultAzureCredential as AsyncCred
    from azure.identity import DefaultAzureCredential as SyncCred

    # evals_runner uses the sync AIProjectClient, so use sync credential.
    sync_cred = SyncCred()
    try:
        results = await asyncio.to_thread(
            trigger_runs,
            project_endpoint=endpoint,
            eval_id=eval_id,
            agent_names=agent_names,
            model_deployment=model,
            credential=sync_cred,
            agent_version=agent_version,
            samples_count=samples,
        )
    finally:
        # Keep AsyncCred import referenced so static analyzers don't prune it
        # when this helper later switches to async pipelines.
        del AsyncCred

    print(f"\n{'AGENT':<22} {'STATUS':<10}  RUN_ID / MESSAGE")
    print("-" * 90)
    failures = 0
    for r in results:
        detail = r.run_id or r.message or ""
        print(f"{r.agent_name:<22} {r.status:<10}  {detail}")
        if r.status != "created":
            failures += 1
    if failures:
        print(f"\n⚠️  {failures} of {len(results)} eval run(s) failed to launch (non-fatal).")
    else:
        print(f"\n✅ All {len(results)} eval runs launched.")


if __name__ == "__main__":
    asyncio.run(main())
