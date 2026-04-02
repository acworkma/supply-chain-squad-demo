# Architecture

Technical deep dive into how the Patient Flow & Bed Management demo is built.

## System Overview

```mermaid
graph TD
    UI[React Control Tower UI] -->|REST polling + SSE streams| API[FastAPI Backend]
    API --> ORCH[Orchestrator — Supervisor Pattern]

    ORCH --> FC[Bed Coordinator Assistant]
    ORCH --> PC[Predictive Capacity]
    ORCH --> BA[Bed Allocation]
    ORCH --> EVS[EVS Tasking]
    ORCH --> TO[Transport Ops]
    ORCH --> PS[Policy & Safety]

    FC -->|tool calls| TOOLS[Tool Functions]
    PC -->|tool calls| TOOLS
    BA -->|tool calls| TOOLS
    EVS -->|tool calls| TOOLS
    TO -->|tool calls| TOOLS
    PS -->|tool calls| TOOLS

    TOOLS --> STATE[(State Store)]
    TOOLS --> ES[Event Store]
    TOOLS --> MS[Message Store]

    ES -->|SSE /api/events/stream| UI
    MS -->|SSE /api/agent-messages/stream| UI
    STATE -->|GET /api/state| UI

    style UI fill:#1e293b,stroke:#38bdf8,color:#f8fafc
    style ORCH fill:#312e81,stroke:#818cf8,color:#f8fafc
    style STATE fill:#064e3b,stroke:#34d399,color:#f8fafc
    style TOOLS fill:#713f12,stroke:#fbbf24,color:#f8fafc
```

## Key Design Decisions

### Supervisor Pattern

The orchestrator acts as a central dispatcher. The Bed Coordinator Assistant is the "supervisor" — it aggregates relevant signals, surfaces recommendations, and delegates to specialist agents. All inter-agent communication routes through the orchestrator, never directly agent-to-agent.

This makes the agent workflow observable: every delegation and response shows up in the Agent Conversation panel.

### Tool-Backed Mutations

Agents **cannot** modify state directly. They call named tools like `reserve_bed`, `schedule_transport`, `create_task`, etc. The orchestrator dispatches these calls to deterministic functions in `src/api/app/tools/tool_functions.py`.

Why: This gives us an audit trail, enforces state machine validation on every transition, and means agents can only do things we've explicitly allowed.

### In-Memory State

All state (beds, patients, tasks, transports, reservations) lives in memory. There is no database. State is seeded on startup and reset when a scenario triggers.

Why: This is a demo. Simplicity over durability. The state store uses async locks for thread safety and enforces valid state transitions (e.g., a bed can go READY → RESERVED but not READY → OCCUPIED directly).

### Event Sourcing Lite

Every state mutation emits an event to the Event Store. Events are append-only with monotonic sequence numbers. The UI subscribes to an SSE stream to receive events in real time.

This is "lite" because we don't rebuild state from events — the State Store is the source of truth, and events are a side effect for observability.

### Dual Mode (Simulated vs Live)

The orchestrator auto-detects which mode to use:

- **No Azure config** → Simulated mode: scripted tool call sequences that walk through the demo flow deterministically
- **`PROJECT_ENDPOINT` or `PROJECT_CONNECTION_STRING` set** → Live mode: real Azure AI Foundry agents with GPT-5.2 making decisions

Both modes use the same tool functions, state store, and event system. The only difference is who decides which tools to call.

## Data Model

### Entities

| Entity | Key Fields | State Machine |
|--------|-----------|---------------|
| **Bed** | id, unit, room, letter, state, patient_id | READY → RESERVED → OCCUPIED → DIRTY → CLEANING → READY (+ BLOCKED branch) |
| **Patient** | id, name, mrn, state, acuity, location | AWAITING_BED → BED_ASSIGNED → TRANSPORT_READY → IN_TRANSIT → ARRIVED |
| **Task** | id, type, subject_id, state, priority | PENDING → ACCEPTED → IN_PROGRESS → COMPLETED (+ ESCALATED branch) |
| **Transport** | id, patient_id, from/to, state, priority | Same as Task |
| **Reservation** | id, bed_id, patient_id, is_active, expires | Active/inactive (time-bounded) |

### Events

Events are immutable records with: `id`, `sequence`, `timestamp`, `event_type`, `entity_id`, `payload`, and optional `state_diff`.

16 event types cover the full lifecycle: `PatientBedRequestCreated`, `BedReserved`, `BedStateChanged`, `TaskCreated`, `TransportScheduled`, `PlacementComplete`, etc.

### Agent Messages

Each message includes: `agent_name`, `agent_role`, `content`, `intent_tag`, and `timestamp`. Intent tags categorize the action: `PROPOSE`, `VALIDATE`, `EXECUTE`, `ESCALATE`.

## Tool Functions

10 registered tools, split into read-only and mutation:

**Read-only:** `get_patient`, `get_beds`, `get_tasks`

**Mutation:** `reserve_bed`, `release_bed_reservation`, `create_task`, `update_task`, `schedule_transport`, `publish_event`, `escalate`

Each agent has a scoped set of tools defined in `src/api/app/tools/tool_schemas.py`. The Bed Coordinator Assistant gets everything; specialist agents get only what they need.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check for container probes |
| GET | `/api/state` | Full state snapshot (polled every 2s by UI) |
| GET | `/api/events` | Event list (with `since` param) |
| GET | `/api/events/stream` | SSE stream of events |
| GET | `/api/agent-messages` | Message list (with `since` param) |
| GET | `/api/agent-messages/stream` | SSE stream of agent messages |
| POST | `/api/scenario/seed` | Reset state and seed initial hospital data |
| POST | `/api/scenario/er-admission` | Trigger ER admission (returns 202) |
| POST | `/api/scenario/disruption-replan` | Trigger disruption scenario (returns 202) |
| POST | `/api/scenario/evs-gated` | Trigger EVS-gated placement — bed requires cleaning first (returns 202) |
| POST | `/api/scenario/or-admission` | Trigger OR admission — post-surgical patient (returns 202) |
| POST | `/api/scenario/unit-transfer` | Trigger unit-to-unit transfer (returns 202) |

## Frontend Architecture

React 18 + TypeScript + Tailwind CSS + Vite.

- **`useApi` hook** — Polls `/api/state` every 2 seconds for bed/patient/transport state
- **`useSSE` hook** — Maintains persistent SSE connections for real-time events and agent messages
- **Three-pane layout** — `ControlTower` component splits into Ops Dashboard (left, 55%) and Agent Conversation + Event Timeline (right, 45%)
- **ScenarioToolbar** — Trigger buttons for scenarios + connection status indicator

## Infrastructure (Azure)

Provisioned via Bicep in `infra/`:

| Module | Resources |
|--------|-----------|
| `foundry.bicep` | AI Services, AI Hub, AI Project, model deployment |
| `aca.bicep` | Container Registry, Container App Environment, Container App, RBAC |
| `observability.bicep` | Log Analytics workspace, Application Insights |

Single-container deployment: the Docker image serves both the FastAPI API and the static React build.

## Project Structure

```
├── azure.yaml                      # azd project config
├── Dockerfile                      # Multi-stage build (React → Python)
├── infra/
│   ├── main.bicep                  # Orchestrates all modules
│   └── modules/
│       ├── foundry.bicep           # AI Foundry resources
│       ├── aca.bicep               # Container Apps + registry
│       └── observability.bicep     # Logging + monitoring
├── scripts/
│   ├── build_agents.py             # Creates/updates Foundry agents
│   └── smoke_test.sh               # Post-deploy health check
└── src/
    ├── api/
    │   ├── app/
    │   │   ├── agents/
    │   │   │   ├── orchestrator.py # Dual-mode orchestration engine
    │   │   │   └── prompts/        # 6 agent system prompts
    │   │   ├── events/             # Event store + SSE
    │   │   ├── messages/           # Message store + SSE
    │   │   ├── models/             # Pydantic models, enums, transitions
    │   │   ├── routers/            # FastAPI route handlers
    │   │   ├── state/              # In-memory state store + seed data
    │   │   └── tools/              # Tool implementations + JSON schemas
    │   └── tests/                  # 344 tests (models, state, tools, endpoints, scenarios)
    └── ui/
        └── src/
            ├── components/         # Dashboard, Conversation, Timeline
            ├── hooks/              # useApi, useSSE
            └── types/              # TypeScript interfaces
```
