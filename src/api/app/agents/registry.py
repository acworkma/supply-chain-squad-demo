"""Persistent Foundry agent registry.

Provides two responsibilities:

1. **Deploy-time registration** (``sync_agents``): Create or update each agent
   as a persistent ``PromptAgentDefinition`` version in the target Foundry
   project. Called by ``scripts/build_agents.py`` during ``azd`` postprovision
   so agents show up in the Microsoft Foundry portal.

2. **Runtime lookup** (``resolve_agent_versions``): At FastAPI startup, map
   each agent name to its latest version so the orchestrator can invoke it.
   Never creates or updates agents at runtime.

All five agents are registered:
``supply-coordinator``, ``supply-scanner``, ``catalog-sourcer``,
``order-manager``, ``compliance-gate``.

Source of truth for prompts: ``src/api/app/agents/prompts/{name}.txt``.
Source of truth for tools: ``src/api/app/tools/tool_schemas.py::AGENT_TOOLS_V2``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
from azure.core.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

logger = logging.getLogger(__name__)


# Canonical agent list (order matters for deterministic registration output).
AGENT_NAMES: list[str] = [
    "supply-coordinator",
    "supply-scanner",
    "catalog-sourcer",
    "order-manager",
    "compliance-gate",
]

# Optional short descriptions surfaced in the Foundry portal agent list.
AGENT_DESCRIPTIONS: dict[str, str] = {
    "supply-coordinator": "Supervisor agent — coordinates the hospital supply-closet replenishment workflow.",
    "supply-scanner": "Scans hospital supply closets and identifies items below par level.",
    "catalog-sourcer": "Looks up vendor catalogs and recommends the best vendor for reorder.",
    "order-manager": "Executes purchase-order lifecycle: create, submit, ship, receive.",
    "compliance-gate": "Validates critical shortages and approves purchase orders ≥$1000.",
}

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class AgentRegistration:
    """Result of registering a single agent."""

    agent_name: str
    version: str
    status: str  # "created", "updated", "unchanged"
    prompt_preview: str


@dataclass(frozen=True)
class ResolvedAgent:
    """Agent name → version mapping used at runtime."""

    agent_name: str
    version: str


def _load_prompt(agent_name: str) -> str:
    """Load an agent's system prompt verbatim from the prompts/ directory."""
    return (_PROMPTS_DIR / f"{agent_name}.txt").read_text(encoding="utf-8")


def _build_agent_definition(
    agent_name: str,
    model_deployment: str,
    tools: list[FunctionTool] | None = None,
) -> PromptAgentDefinition:
    """Build a ``PromptAgentDefinition`` from local sources.

    Imports ``AGENT_TOOLS_V2`` lazily to avoid pulling heavy modules at
    registration time.
    """
    if tools is None:
        # Lazy import: registry.py is imported early by build_agents.py,
        # before the full api package is ready.
        from ..tools.tool_schemas import AGENT_TOOLS_V2

        tools = list(AGENT_TOOLS_V2.get(agent_name, []))

    instructions = _load_prompt(agent_name)
    return PromptAgentDefinition(
        model=model_deployment,
        instructions=instructions,
        tools=tools,
    )


def _definition_fingerprint(definition: PromptAgentDefinition) -> str:
    """Stable SHA-256 hash of an agent definition for change detection."""
    payload = json.dumps(definition.as_dict(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _existing_fingerprints(
    client: AIProjectClient, agent_name: str
) -> dict[str, str]:
    """Return ``{version_id: fingerprint}`` for all existing versions.

    Returns an empty dict if the agent does not exist yet.
    """
    result: dict[str, str] = {}
    try:
        async for version in client.agents.list_versions(agent_name):
            # AgentVersionDetails contains the definition under ``definition``.
            defn = getattr(version, "definition", None)
            if defn is None:
                continue
            try:
                payload = json.dumps(defn.as_dict(), sort_keys=True, ensure_ascii=False)
            except AttributeError:
                payload = json.dumps(defn, sort_keys=True, ensure_ascii=False, default=str)
            ver = getattr(version, "version", None) or getattr(version, "id", "unknown")
            result[str(ver)] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    except ResourceNotFoundError:
        pass
    return result


async def sync_agent(
    client: AIProjectClient,
    agent_name: str,
    model_deployment: str,
) -> AgentRegistration:
    """Create or update a single persistent agent.

    Strategy:
        - Build definition from local prompt + tool schemas.
        - If no versions exist → create first version.
        - If newest existing version has identical fingerprint → unchanged.
        - Otherwise → create a new version (Foundry keeps history).
    """
    definition = _build_agent_definition(agent_name, model_deployment)
    new_fp = _definition_fingerprint(definition)
    prompt_preview = (_load_prompt(agent_name)[:80] + "...").replace("\n", " ")

    existing = await _existing_fingerprints(client, agent_name)
    if not existing:
        # Agent has never been registered; create first version.
        version_details = await client.agents.create_version(
            agent_name,
            definition=definition,
            description=AGENT_DESCRIPTIONS.get(agent_name),
        )
        version = str(getattr(version_details, "version", "1"))
        return AgentRegistration(agent_name, version, "created", prompt_preview)

    if new_fp in existing.values():
        # Definition unchanged; reuse newest version.
        newest = max(existing.keys())
        return AgentRegistration(agent_name, newest, "unchanged", prompt_preview)

    # Definition changed; create a new version (old versions remain in Foundry).
    version_details = await client.agents.create_version(
        agent_name,
        definition=definition,
        description=AGENT_DESCRIPTIONS.get(agent_name),
    )
    version = str(getattr(version_details, "version", "new"))
    return AgentRegistration(agent_name, version, "updated", prompt_preview)


async def sync_agents(
    endpoint: str,
    credential: "AsyncTokenCredential",
    model_deployment: str,
    agent_names: list[str] | None = None,
) -> list[AgentRegistration]:
    """Register or update all agents. Returns per-agent status records."""
    names = agent_names or AGENT_NAMES
    results: list[AgentRegistration] = []
    async with AIProjectClient(endpoint=endpoint, credential=credential) as client:
        for name in names:
            try:
                reg = await sync_agent(client, name, model_deployment)
                logger.info(
                    "agent=%s version=%s status=%s prompt=%r",
                    reg.agent_name, reg.version, reg.status, reg.prompt_preview,
                )
                results.append(reg)
            except Exception as exc:
                logger.exception("Failed to register agent %s: %s", name, exc)
                raise
    return results


async def resolve_agent_versions(
    endpoint: str,
    credential: "AsyncTokenCredential",
    agent_names: list[str] | None = None,
) -> dict[str, str]:
    """Startup lookup: return ``{agent_name: latest_version}``.

    Raises ``ResourceNotFoundError`` if any expected agent has no versions,
    which signals that the deploy-time registration step did not run.
    """
    names = agent_names or AGENT_NAMES
    resolved: dict[str, str] = {}
    async with AIProjectClient(endpoint=endpoint, credential=credential) as client:
        for name in names:
            versions = [v async for v in client.agents.list_versions(name, limit=1)]
            if not versions:
                raise ResourceNotFoundError(
                    f"Agent '{name}' has no versions. Run scripts/build_agents.py."
                )
            resolved[name] = str(getattr(versions[0], "version", "1"))
    return resolved
