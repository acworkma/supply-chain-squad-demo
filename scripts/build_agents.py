"""Build and register AI agents in Azure AI Foundry.

Supply Chain Management Demo — creates the supervisor + specialist agents.
This script runs as a post-provision hook after `azd provision`.

TODO: Implement agent creation for supply chain domain.
"""

import os
import sys


def main():
    project_conn = os.environ.get("PROJECT_CONNECTION_STRING", "")
    if not project_conn:
        print("⚠️  PROJECT_CONNECTION_STRING not set — skipping agent creation.")
        print("   Run `azd provision` first, or set the env var manually.")
        sys.exit(0)

    print("🔧 Supply Chain agent creation — not yet implemented.")
    print(f"   Project: {project_conn.split(';')[0] if project_conn else 'N/A'}")
    print("   Agents to create: supply-coordinator, order-fulfillment,")
    print("   inventory-manager, logistics-planner, demand-forecaster, disruption-handler")


if __name__ == "__main__":
    main()
