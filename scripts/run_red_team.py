"""On-demand CLI to launch Foundry red-team runs for demo agents.

Examples:
    # Dry-run: print the request bodies for all 5 agents, do not submit
    python scripts/run_red_team.py --dry-run

    # Dry-run for a single agent
    python scripts/run_red_team.py compliance-gate --dry-run

    # Submit runs for all 5 agents
    python scripts/run_red_team.py

    # Submit a run for just one agent
    python scripts/run_red_team.py supply-coordinator

    # Submit with a broader scan (overrides defaults)
    python scripts/run_red_team.py compliance-gate \\
        --risk-categories HateUnfairness Violence Sexual \\
        --attack-strategies easy moderate \\
        --num-turns 2

Required env vars (populated by ``azd env get-values``):
    PROJECT_ENDPOINT        — Foundry project endpoint
    MODEL_DEPLOYMENT_NAME   — target model deployment

Optional:
    FOUNDRY_AGENT_VERSION   — override agent version tag (default "2")
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Allow importing red_team_runner and the app's agent registry.
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent / "src" / "api"))

from red_team_runner import (  # noqa: E402
    DEFAULT_ATTACK_STRATEGIES,
    DEFAULT_NUM_TURNS,
    DEFAULT_RISK_CATEGORIES,
    build_all_configs,
    resolve_model_deployment,
    resolve_project_endpoint,
    trigger_red_teams,
)


def _all_agent_names() -> list[str]:
    """Load canonical agent names from the app's registry."""
    try:
        # type: ignore[import-not-found]
        from app.agents.registry import AGENT_NAMES

        return list(AGENT_NAMES)
    except Exception:
        # Fallback if registry import fails (e.g. missing app deps).
        return [
            "supply-coordinator",
            "supply-scanner",
            "catalog-sourcer",
            "order-manager",
            "compliance-gate",
        ]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Launch Foundry red-team runs for demo agents.")
    p.add_argument(
        "agents",
        nargs="*",
        help="Agent name(s) to scan. Omit or use 'all' to scan every registered agent.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the request bodies, but do not submit.",
    )
    p.add_argument(
        "--risk-categories",
        nargs="+",
        default=list(DEFAULT_RISK_CATEGORIES),
        metavar="CATEGORY",
        help="RiskCategory enum values (e.g. HateUnfairness Violence Sexual SelfHarm).",
    )
    p.add_argument(
        "--attack-strategies",
        nargs="+",
        default=list(DEFAULT_ATTACK_STRATEGIES),
        metavar="STRATEGY",
        help="AttackStrategy enum values (e.g. easy moderate difficult jailbreak).",
    )
    p.add_argument(
        "--num-turns",
        type=int,
        default=DEFAULT_NUM_TURNS,
        help=f"Simulation rounds per probe (default {DEFAULT_NUM_TURNS}).",
    )
    p.add_argument(
        "--simulation-only",
        action="store_true",
        help="Produce conversations only (no evaluator scoring).",
    )
    p.add_argument(
        "--agent-version",
        default=os.environ.get("FOUNDRY_AGENT_VERSION", "2"),
        help="Agent version tag to stamp onto each run (default '2').",
    )
    return p.parse_args()


async def _amain() -> int:
    args = _parse_args()

    registered = _all_agent_names()
    selection = args.agents or ["all"]
    if len(selection) == 1 and selection[0].lower() == "all":
        targets = registered
    else:
        unknown = [a for a in selection if a not in registered]
        if unknown:
            print(
                f"ERROR: unknown agent(s): {', '.join(unknown)}", file=sys.stderr)
            print(f"Known agents: {', '.join(registered)}", file=sys.stderr)
            return 2
        targets = selection

    endpoint = resolve_project_endpoint()
    model = resolve_model_deployment()
    if not endpoint:
        print(
            "ERROR: PROJECT_ENDPOINT is not set (run: azd env get-values).", file=sys.stderr)
        return 2
    if not model:
        print("ERROR: MODEL_DEPLOYMENT_NAME is not set (run: azd env get-values).", file=sys.stderr)
        return 2

    configs = build_all_configs(
        agent_names=targets,
        model_deployment=model,
        agent_version=args.agent_version,
        risk_categories=args.risk_categories,
        attack_strategies=args.attack_strategies,
        num_turns=args.num_turns,
        simulation_only=args.simulation_only,
    )

    print(f"Endpoint:          {endpoint}")
    print(f"Model deployment:  {model}")
    print(f"Agent version:     {args.agent_version}")
    print(f"Risk categories:   {', '.join(args.risk_categories)}")
    print(f"Attack strategies: {', '.join(args.attack_strategies)}")
    print(f"Num turns:         {args.num_turns}")
    print(f"Simulation only:   {args.simulation_only}")
    print(f"Agents:            {', '.join(c.agent_name for c in configs)}")
    print()

    if args.dry_run:
        print("DRY-RUN — the following run bodies would be POSTed:\n")
        for cfg in configs:
            print(f"--- {cfg.agent_name} ---")
            print(json.dumps(cfg.body, indent=2))
            print()
        print(f"Built {len(configs)} run config(s). Nothing submitted.")
        return 0

    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    results = await asyncio.to_thread(
        trigger_red_teams,
        project_endpoint=endpoint,
        configs=configs,
        credential=credential,
    )

    print(f"{'AGENT':<22} {'STATUS':<10}  RUN_ID / MESSAGE")
    print("-" * 90)
    failures = 0
    for r in results:
        detail = r.run_id or r.message or ""
        print(f"{r.agent_name:<22} {r.status:<10}  {detail}")
        if r.status != "created":
            failures += 1
    if failures:
        print(
            f"\n⚠️  {failures} of {len(results)} red-team run(s) failed to launch.")
        return 1
    print(f"\n✅ All {len(results)} red-team runs launched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain()))
