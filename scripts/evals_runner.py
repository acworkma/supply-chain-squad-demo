"""Launch Foundry evaluation runs for each persistent agent.

Given a pre-authored Foundry ``eval`` template (created once in the portal with
all desired built-in evaluators), this module POSTs a new ``eval.run`` for
each of the five supply-chain demo agents, using synthetic data generation as
the data source. Each run targets ``azure_ai_agent`` with the agent's
registered name/version.

REST contract (New Foundry, OpenAI-compatible evals API):
    POST {PROJECT_ENDPOINT}/openai/evals/{eval_id}/runs?api-version=2025-11-15-preview
    Body:
        {
          "name": "<display-name>",
          "data_source": {
            "type": "azure_ai_synthetic_data_gen_preview",
            "item_generation_params": {
              "type": "synthetic_data_gen_preview",
              "samples_count": <int>,
              "prompt": "<generator-prompt>",
              "model_deployment_name": "<deployment>",
              "output_dataset_name": "<unique-name>",
              "sources": [],
              "data_mapping": {"query": "{{item.query}}"}
            },
            "target": {
              "type": "azure_ai_agent",
              "name": "<agent-name>",
              "version": "<agent-version>",
              "tool_descriptions": []
            }
          },
          "metadata": {"trigger_type": "oneoff"}
        }
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Sequence

EVAL_API_VERSION = "2025-11-15-preview"

# Per-agent synthetic data generation prompts. Kept concise — Foundry's
# generator expands these into ~N test queries.
AGENT_PROMPTS: dict[str, str] = {
    "supply-coordinator": (
        "Generate realistic user queries used to test a supply-coordinator "
        "agent that orchestrates medical supply reorder decisions across "
        "multiple hospital units, including PAR-level triggers, vendor tier "
        "selection (GPO_CONTRACT > PREFERRED > SPOT_BUY), and escalation to "
        "compliance review for purchase orders at or above $1,000."
    ),
    "supply-scanner": (
        "Generate realistic user queries used to test a supply-scanner agent "
        "that inventories medical supplies via vision, detects PAR-level "
        "shortages, flags critical items, and hands off to the supply "
        "coordinator for reorder planning."
    ),
    "catalog-sourcer": (
        "Generate realistic user queries used to test a catalog-sourcer agent "
        "that searches vendor catalogs for medical supplies, compares pricing "
        "across vendor tiers, checks stock availability, and recommends the "
        "best vendor + SKU match for a reorder."
    ),
    "order-manager": (
        "Generate realistic user queries used to test an order-manager agent "
        "that creates, tracks, and updates purchase orders for medical "
        "supplies, routes POs at or above $1,000 to compliance for approval, "
        "and returns order status summaries."
    ),
    "compliance-gate": (
        "Generate realistic user queries used to test a compliance-gate agent "
        "that validates critical shortage handling, reviews purchase orders "
        "at or above $1,000, and approves or rejects them based on vendor "
        "tier, quantity, and unit cost thresholds."
    ),
}


@dataclass
class EvalRunResult:
    agent_name: str
    status: str  # "created", "skipped", or "failed"
    run_id: str | None = None
    message: str | None = None


def build_run_body(
    *,
    agent_name: str,
    agent_version: str,
    model_deployment: str,
    samples_count: int,
    dataset_suffix: str,
) -> dict:
    """Construct the request body for POST /openai/evals/{eval_id}/runs."""
    prompt = AGENT_PROMPTS.get(agent_name)
    if prompt is None:
        raise ValueError(f"No synthetic-gen prompt registered for agent '{agent_name}'")
    return {
        "name": agent_name,
        "data_source": {
            "type": "azure_ai_synthetic_data_gen_preview",
            "item_generation_params": {
                "type": "synthetic_data_gen_preview",
                "samples_count": samples_count,
                "prompt": prompt,
                "model_deployment_name": model_deployment,
                "output_dataset_name": f"scdemo-eval-{agent_name}-{dataset_suffix}",
                "sources": [],
                "data_mapping": {"query": "{{item.query}}"},
            },
            "target": {
                "type": "azure_ai_agent",
                "name": agent_name,
                "version": agent_version,
                "tool_descriptions": [],
            },
        },
        "metadata": {"trigger_type": "oneoff"},
    }


def trigger_runs(
    *,
    project_endpoint: str,
    eval_id: str,
    agent_names: Sequence[str],
    model_deployment: str,
    credential,
    agent_version: str = "1",
    agent_versions: dict[str, str] | None = None,
    samples_count: int = 15,
) -> list[EvalRunResult]:
    """POST one eval run per agent. Soft-fails per agent.

    ``agent_versions`` (if provided) maps agent name → version; overrides the
    fallback ``agent_version`` for any agent present in the map.

    Uses ``azure.ai.projects.AIProjectClient.send_request`` so we inherit
    retry/auth from the same pipeline the registration script uses.
    """
    from azure.ai.projects import AIProjectClient
    from azure.core.rest import HttpRequest

    client = AIProjectClient(endpoint=project_endpoint, credential=credential)
    suffix = str(int(time.time()))
    url = f"{project_endpoint}/openai/evals/{eval_id}/runs?api-version={EVAL_API_VERSION}"
    versions = agent_versions or {}

    results: list[EvalRunResult] = []
    for agent_name in agent_names:
        try:
            body = build_run_body(
                agent_name=agent_name,
                agent_version=versions.get(agent_name, agent_version),
                model_deployment=model_deployment,
                samples_count=samples_count,
                dataset_suffix=suffix,
            )
            resp = client.send_request(HttpRequest("POST", url, json=body))
            if 200 <= resp.status_code < 300:
                payload = resp.json()
                results.append(
                    EvalRunResult(
                        agent_name=agent_name,
                        status="created",
                        run_id=payload.get("id"),
                    )
                )
            else:
                results.append(
                    EvalRunResult(
                        agent_name=agent_name,
                        status="failed",
                        message=f"HTTP {resp.status_code}: {resp.text()[:200]}",
                    )
                )
        except Exception as exc:  # noqa: BLE001 — soft-fail per agent
            results.append(
                EvalRunResult(
                    agent_name=agent_name,
                    status="failed",
                    message=f"{type(exc).__name__}: {exc}",
                )
            )
    return results


def bootstrap_enabled() -> bool:
    """Return False if FOUNDRY_BOOTSTRAP_EVALS is explicitly set to false."""
    raw = os.environ.get("FOUNDRY_BOOTSTRAP_EVALS", "true").strip().lower()
    return raw not in {"false", "0", "no", "off"}


def resolve_eval_id() -> str | None:
    """Return the portal-authored eval template ID or None if unset."""
    value = os.environ.get("FOUNDRY_EVAL_ID", "").strip()
    return value or None
