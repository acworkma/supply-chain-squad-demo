# Supply Chain Management — Agentic AI Demo

Multi-agent AI system for supply chain management operations, built with Azure AI Foundry and Azure Container Apps.

## What This Demonstrates

AI agents collaborating to manage supply chain operations in real-time:

- **Order Fulfillment** — Processing, allocation, picking, and shipping
- **Inventory Management** — Stock levels, reorder triggers, warehouse allocation
- **Logistics Planning** — Shipment routing, carrier selection, ETA calculation
- **Demand Forecasting** — Predictive demand analysis, seasonal patterns
- **Disruption Handling** — Risk assessment, rerouting, escalation

All orchestrated by a supervisor agent through a dark-themed "Command Center" UI.

## Architecture

| Layer | Stack |
|-------|-------|
| **Frontend** | React, TypeScript, Tailwind CSS, SSE |
| **Backend** | Python, FastAPI, Azure AI Projects SDK |
| **Agents** | Azure AI Foundry (supervisor + 5 specialists) |
| **Infrastructure** | Azure Container Apps, ACR, Bicep, azd |
| **Observability** | Log Analytics, Application Insights |

## Quick Start

```bash
# Local development
cd src/api && pip install -e '.[dev]' && uvicorn app.main:app --reload
cd src/ui && npm install && npm run dev

# Deploy to Azure
azd up
```

## Project Status

🚧 **Scaffold phase** — Directory structure, build configs, Azure infra, and UI shell are in place. Domain model and agent implementation are next.

## License

MIT
