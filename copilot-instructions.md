# Supply Chain Management — Agentic AI Demo

## Copilot Instructions

This project demonstrates multi-agent AI orchestration for supply chain management using Azure AI Foundry.

### Architecture

- **Backend:** Python/FastAPI (`src/api/`) — domain model, agent orchestration, event sourcing
- **Frontend:** React/TypeScript/Tailwind (`src/ui/`) — dark-mode "command center" UI with real-time SSE updates
- **Infrastructure:** Azure Container Apps + Azure AI Foundry (`infra/`) — Bicep templates, managed identity, keyless auth
- **Agents:** Azure AI Foundry agents with tool-calling — supervisor orchestration pattern

### Key Architectural Invariants

1. **Tool-backed state mutation:** Agent tool functions are the single mutation boundary. Each tool validates, transitions state, emits an event. No direct state mutation.
2. **Supervisor orchestration:** Supply Chain Coordinator routes to specialist agents. No peer-to-peer agent communication.
3. **Event sourcing lite:** Append-only event store with sequence numbers. State materialized alongside events.
4. **In-memory state:** No database. State resets on container restart. Acceptable for demo scope.
5. **Single container:** React built to static files, served by FastAPI. One ACA container, one ingress.

### File Layout

```
src/api/app/
  agents/         — orchestrator + prompts
  events/         — append-only event store
  messages/       — agent conversation store
  metrics/        — scenario run metrics
  models/         — domain entities, enums, state machines
  routers/        — FastAPI endpoints
  state/          — in-memory state store
  tools/          — agent tool functions + schemas
  config.py       — Pydantic settings
  config_store.py — runtime config overlay
  main.py         — FastAPI app

src/ui/src/
  components/     — React components (layout, dashboard, conversation, timeline)
  hooks/          — useApi, useSSE
  lib/            — utilities, color mappings
  types/          — TypeScript interfaces

infra/
  main.bicep       — orchestration
  modules/
    aca.bicep        — Container Apps + ACR + identity
    foundry.bicep    — AI Services + model deployments + project
    observability.bicep — Log Analytics + App Insights
```

### Testing

- **Backend:** `cd src/api && pytest` (asyncio mode auto, httpx test client)
- **Frontend:** `cd src/ui && npm test` (Vitest + Testing Library)
- **Smoke:** `scripts/smoke_test.sh` (curl-based endpoint verification)

### Local Development

```bash
# Backend
cd src/api && pip install -e '.[dev]' && uvicorn app.main:app --reload

# Frontend
cd src/ui && npm install && npm run dev

# Deploy to Azure
azd up
```
