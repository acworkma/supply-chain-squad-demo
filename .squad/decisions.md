# Squad Decisions

## Active Decisions

### ADR-001: In-Memory State Store (No Database)
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- Use Python in-memory dicts (asyncio locks). No database. State resets on container restart. Acceptable for demo scope.

### ADR-002: Event Sourcing Lite — Dual-Write State + Events
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- Append-only event store with monotonic sequence numbers. State is materialized in-memory alongside events. Not full replay-based event sourcing.

### ADR-003: Tool-Backed State Mutation — Agents Never Mutate Directly
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- Agent tool functions are the single mutation boundary. Each tool validates, transitions state, emits event. Core architectural invariant.

### ADR-003a: Tools as Pure Functions with Store Arguments
- **Author:** Goose | **Date:** 2026-03-07 | **Status:** Implemented
- Standalone async functions in `tool_functions.py` receive `state_store`, `event_store`, `message_store` as kwargs. Stateless, testable, maps to Foundry function-calling pattern. Orchestrator injects singleton stores at dispatch time.

### ADR-004: Supervisor Orchestration Pattern
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- Flow Coordinator as supervisor routes to specialists. Single decision point, no peer-to-peer agent communication. Specialists are stateless per invocation.

### ADR-005: Single Container, Two Processes (API + Static UI)
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- React built to static files, served by FastAPI at `/`. API at `/api/*`. One ACA container, one ingress, one URL.

### ADR-006: SSE for Real-Time UI Updates
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- Server-Sent Events from FastAPI. Native browser EventSource. Simpler than WebSockets for uni-directional streaming.

### ADR-007: Scenario Reset on Trigger
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- Each scenario endpoint clears all state, seeds initial data, runs orchestration async. 202 Accepted. Mutex for concurrent run prevention.

### ADR-008: Agent System Prompts as Files + Tool Schemas from Python Types
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- Prompts in `src/api/app/agents/prompts/*.txt`. Tool definitions from Python annotations → Foundry schemas. `build_agents.py` creates/updates agents.

### ADR-009: Chat Transcript Model with Intent Tags
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- `AgentMessage` with intentTag (PROPOSE/VALIDATE/EXECUTE/ESCALATE). Rule-based tag assignment initially. Messages append-only, linked to events via relatedEventIds.

### ADR-010: Predictive Capacity as Simulated Confidence Scores
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- Deterministic scores based on bed state + scenario script. LLM generates reasoning narrative. Not real ML.

### INFRA-001: Keyless Auth & Security Posture
- **Author:** Iceman | **Date:** 2026-03-07 | **Status:** Implemented
- `disableLocalAuth: true` on AI Services — Entra ID only. ACR admin disabled — AcrPull via managed identity. OIDC federated credentials for CI/CD (no stored secrets). Container resources: 0.5 CPU, 1Gi, scale 0-1.

### UI-001: Frontend Data Architecture — Props-Down from ControlTower
- **Author:** Viper | **Date:** 2026-03-07 | **Status:** Implemented
- ControlTower is the single data owner (useApi + useSSE). Props down one level to leaf components. Color mapping centralized in `lib/colors.ts`. Components are pure renderers.

### PLAN-001: Spec Decomposition — 23 Work Items across 4 Phases
- **Author:** Maverick | **Date:** 2026-03-07 | **Status:** Implemented
- Phase 1 (Foundation): WI-001 through WI-006 — scaffold, domain model, events, infra, UI shell, tests
- Phase 2 (Core): WI-007 through WI-013 — API endpoints, tools, build_agents, 3 UI panes, ACA deploy config
- Phase 3 (Integration): WI-014 through WI-018 — orchestration loop, scenarios A+B, frontend-backend wiring, domain tests
- Phase 4 (Polish): WI-019 through WI-023 — CI/CD, e2e tests, smoke test, UI polish, optional policy agent
- Critical path: WI-001→WI-002/003→WI-007/008→WI-014→WI-015/016
- **All 23 WIs verified complete against actual codebase — 2026-03-09.**

### RENAME-001: Scenario Rename — happy-path → er-admission
- **Authors:** Goose, Maverick | **Date:** 2026-03-27 | **Status:** Implemented
- Renamed the "happy-path" scenario to "er-admission" across all layers: API route (`/api/scenario/er-admission`), orchestrator dispatch, router functions, test classes/URLs/assertions, frontend toolbar label+endpoint, docs, eval scripts, eval result JSON files, and smoke test. Aligns with domain-specific naming convention used by sibling scenarios (or-admission, evs-gated, unit-transfer). 391 backend tests pass.

### METRICS-001: Metrics Endpoint Returns 200 for Empty State
- **Author:** Goose | **Date:** 2026-03-09 | **Status:** Implemented
- `GET /api/metrics` and `GET /api/metrics/history` return HTTP 200 with `{"message": "No scenario runs recorded yet"}` when no metrics exist. Frontend checks for `message` key to detect empty state.

### METRICS-002: Per-Agent Metrics via Inline Instrumentation
- **Author:** Goose | **Date:** 2026-03-09 | **Status:** Implemented
- Instrument `_invoke_agent` inside `orchestrator.py` directly. `AgentMetrics`/`ScenarioMetrics` as TypedDicts in same file. Token counts accumulated across multi-round tool loops. Simulated functions return zero-token metrics with real latency.

### CONFIG-001: Runtime Config Store as Transparent Overlay
- **Author:** Goose | **Date:** 2026-03-10 | **Status:** Implemented
- `RuntimeConfigStore` singleton overlays env var defaults. `GET /api/config` (effective merged), `PUT /api/config` (partial override), `POST /api/config/reset` (revert). Orchestrator reads from config store abstracting source.

### CI-001: CI Pipeline — Dual-Job Lint+Test
- **Author:** Iceman | **Date:** 2026-03-07 | **Status:** Implemented
- Parallel Python (pytest + ruff) and Frontend (tsc + vite build) jobs. Ruff lint non-blocking (`continue-on-error`) until pre-existing issues resolved. Triggers on PRs to main and pushes to main.

### INFRA-002: Multi-Model Deployment via Array Parameter
- **Author:** Iceman | **Date:** 2026-03-09 | **Status:** Implemented
- Refactored `foundry.bicep` to array-based `modelDeployments` with `@batchSize(1)`. Three models: gpt-5.2 (100K TPM), gpt-4.1 (50K), gpt-5-mini (50K). `primaryModelName` param keeps ACA pointing to gpt-5.2.

### UI-002: useSSE Returns Connection Status Object
- **Author:** Viper | **Date:** 2026-03-07 | **Status:** Implemented
- Changed `useSSE<T>` return from `T[]` to `{ items: T[], connected: boolean }`. SSE hook exposes its own connection state via `onopen`/`onerror`. All consumers updated to destructure.

### STATUS-001: All 23 Work Items Complete
- **Author:** Maverick | **Date:** 2026-03-09 | **Status:** Verified
- Full 4-phase audit: 344 backend tests passing, frontend compiles clean, both orchestration modes operational, CI pipeline in place, smoke test covers full scenario flow. All 10 ADRs confirmed Implemented.

### DESIGN-001: Continuous Demo Mode (Pending)
- **Author:** Maverick | **Date:** 2026-03-10 | **Status:** Pending user answers
- Long-running mode where patients arrive every X minutes until Stop or divert. Design questions raised, awaiting acworkma's answers before implementation begins.

### DOMAIN-P3-001: Supply Chain Domain Model
- **Author:** Maverick | **Date:** 2026-04-02 | **Status:** Implementing
- Full domain pivot from bed management → supply chain (distribution/fulfillment center). 1:1 entity mapping: Patient→Order, Bed→Product, Task→Task, Transport→Shipment, Reservation→Allocation. New enums: OrderState (9 states), ProductState (6 states), ShipmentState (7 states), TaskType (PICK/PACK/QUALITY_CHECK/RESTOCK), FulfillmentPriority (EXPEDITED/HIGH/STANDARD), SourceChannel (ECOMMERCE/WHOLESALE/RETAIL/RETURNS). TaskState and IntentTag unchanged. 10 tools (1:1 mapping). Config: 2 warehouses (east-dc, west-dc), 3 zones (Zone-A Electronics, Zone-B General, Zone-C General). Seed data: 16 products, 5 existing orders. 3 scenarios: standard-fulfillment, supplier-delay, rush-order. All 10 ADRs preserved unchanged.
- **Design doc:** `.squad/decisions/inbox/maverick-supply-chain-domain-model.md` (archived)

### DOMAIN-P3-002: Supply Chain Agent Roster
- **Author:** Maverick | **Date:** 2026-04-02 | **Status:** Implementing
- 6 agents → 6 agents, 1:1 mapping. bed-coordinator→supply-coordinator, predictive-capacity→demand-forecaster, bed-allocation→inventory-allocator, evs-tasking→warehouse-ops, transport-ops→logistics-planner, policy-safety→compliance-monitor. Same supervisor pattern (ADR-004). Per-agent tool sets defined. Prompt files renamed accordingly.
- **Design doc:** `.squad/decisions/inbox/maverick-supply-chain-agent-roster.md` (archived)

### PLAN-P3-001: Phase 3 Work Item Decomposition — 17 WIs
- **Author:** Maverick | **Date:** 2026-04-02 | **Status:** In Progress
- 17 WIs: Goose 9 (WI-P3-001 through WI-P3-009, critical path), Viper 4 (WI-P3-011 through WI-P3-014), Iceman 2 (WI-P3-016, WI-P3-017), Jester 2 (WI-P3-010, WI-P3-015). Critical path: enums→entities→transitions→store→tools→schemas→prompts→orchestrator→scenarios→tests. UI parallelizable after store stabilizes.
- **Design doc:** `.squad/decisions/inbox/maverick-phase3-work-items.md` (archived)

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
