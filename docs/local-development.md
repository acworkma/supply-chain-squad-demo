# Local Development

How to run, develop, and test the demo on your machine.

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| npm | 10+ | `npm --version` |
| Docker | Latest | `docker --version` (optional — only for container testing) |

No Azure account or CLI needed for local development. The app runs in simulated mode by default.

## Quick Start

You need two terminals — one for the API, one for the UI.

**Terminal 1 — Backend API:**

```bash
cd src/api
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The API starts at **http://localhost:8000**. You'll see `Uvicorn running on http://0.0.0.0:8000` in the terminal. The `--reload` flag auto-restarts on code changes.

**Terminal 2 — Frontend UI:**

```bash
cd src/ui
npm install
npm run dev
```

The UI starts at **http://localhost:5173** with hot module replacement. It proxies `/api/*` requests to the backend automatically.

**Open http://localhost:5173** and click the scenario buttons.

## Environment Variables

Copy the sample and edit as needed:

```bash
cp .env.sample .env
```

| Variable | Default | What It Does |
|----------|---------|-------------|
| `PROJECT_ENDPOINT` | *(empty)* | Azure AI Foundry endpoint. Leave empty for simulated mode. |
| `PROJECT_CONNECTION_STRING` | *(empty)* | Alternative to endpoint. Leave empty for simulated mode. |
| `MODEL_DEPLOYMENT_NAME` | `gpt-5.2` | Which model deployment the AI agents use. |
| `APP_THEME` | `dark` | UI theme hint. |

**For local development, you don't need to set any of these.** The defaults run everything in simulated mode.

## Running Tests

### Backend (Python)

```bash
cd src/api

# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_scenarios.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

The test suite includes:
- **Model tests** — entity validation, serialization
- **Transition tests** — state machine rules (valid and invalid transitions)
- **State store tests** — CRUD, locking, seed data
- **Event store tests** — publish, subscribe, sequence numbering
- **Tool function tests** — all 10 tools with edge cases
- **Endpoint tests** — API routes via httpx AsyncClient
- **Scenario tests** — full routine-restock and critical-shortage e2e

### Frontend (React)

```bash
cd src/ui

# Run all tests
npm test

# Run in watch mode
npx vitest
```

### Linting

```bash
cd src/api
ruff check .           # lint
ruff format --check .  # format check
```

## Docker

Build and run the full app in a single container:

```bash
# From repo root
docker build -t supply-closet .
docker run -p 8000:8000 supply-closet
```

Open **http://localhost:8000**. The container serves both the API and the pre-built React UI as static files.

## Project Layout

```
src/
├── api/                    # Python FastAPI backend
│   ├── app/
│   │   ├── main.py         # App entry, CORS, routers, static serving
│   │   ├── config.py       # Pydantic settings from env vars
│   │   ├── agents/
│   │   │   ├── orchestrator.py   # Dual-mode orchestration engine
│   │   │   └── prompts/          # System prompts for each agent
│   │   ├── events/
│   │   │   └── event_store.py    # Append-only event log + SSE
│   │   ├── messages/
│   │   │   └── message_store.py  # Agent message log + SSE
│   │   ├── models/
│   │   │   ├── entities.py       # Item, Closet, PurchaseOrder, etc.
│   │   │   ├── enums.py          # State enums (ItemState, POState, ...)
│   │   │   ├── events.py         # Event model + type constants
│   │   │   └── transitions.py    # State machine validation rules
│   │   ├── routers/
│   │   │   ├── state.py          # GET /api/state
│   │   │   ├── events.py         # GET /api/events + SSE stream
│   │   │   ├── messages.py       # GET /api/agent-messages + SSE stream
│   │   │   └── scenarios.py      # POST scenario triggers
│   │   ├── state/
│   │   │   └── store.py          # In-memory state + seed data
│   │   └── tools/
│   │       ├── tool_functions.py # 10 deterministic tool implementations
│   │       └── tool_schemas.py   # JSON schemas for Foundry agents
│   ├── tests/                    # pytest suite
│   └── pyproject.toml            # Python project config
└── ui/                     # React 18 + TypeScript + Tailwind + Vite
    ├── src/
    │   ├── App.tsx               # Root component
    │   ├── components/
    │   │   ├── layout/           # ControlTower, ScenarioToolbar, PaneHeader
    │   │   ├── dashboard/        # OrderQueue, InventoryBoard, ShipmentTracker
    │   │   ├── conversation/     # AgentConversation
    │   │   └── timeline/         # EventTimeline
    │   ├── hooks/
    │   │   ├── useApi.ts         # State polling hook
    │   │   └── useSSE.ts         # SSE connection hook
    │   ├── types/
    │   │   └── api.ts            # TypeScript interfaces
    │   └── lib/
    │       ├── colors.ts         # Status color mappings
    │       └── utils.ts          # Tailwind merge utility
    ├── package.json
    └── vite.config.ts            # Dev server + API proxy config
```

## Common Tasks

**Add a new tool function:**
1. Implement in `src/api/app/tools/tool_functions.py`
2. Add JSON schema to `src/api/app/tools/tool_schemas.py`
3. Add to the agent's tool set in `tool_schemas.py`
4. Register in `TOOL_DISPATCH` in `src/api/app/agents/orchestrator.py`
5. Add to simulated scenario steps if relevant

**Add a new agent:**
1. Create a prompt file in `src/api/app/agents/prompts/{name}.txt`
2. Add tool mappings in `tool_schemas.py`
3. Add to `AGENT_NAMES` in `scripts/build_agents.py`
4. Add orchestration steps in `orchestrator.py`

**Modify seed data:**
Edit `seed_initial_state()` in `src/api/app/state/store.py`. The initial supply closet inventory is defined there.
