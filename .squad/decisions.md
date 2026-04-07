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

- **Author:** Maverick | **Date:** 2026-04-02 | **Status:** ~~Implementing~~ SUPERSEDED by DOMAIN-C-001
- Full domain pivot from bed management → supply chain (distribution/fulfillment center). 1:1 entity mapping: Patient→Order, Bed→Product, Task→Task, Transport→Shipment, Reservation→Allocation. New enums: OrderState (9 states), ProductState (6 states), ShipmentState (7 states), TaskType (PICK/PACK/QUALITY_CHECK/RESTOCK), FulfillmentPriority (EXPEDITED/HIGH/STANDARD), SourceChannel (ECOMMERCE/WHOLESALE/RETAIL/RETURNS). TaskState and IntentTag unchanged. 10 tools (1:1 mapping). Config: 2 warehouses (east-dc, west-dc), 3 zones (Zone-A Electronics, Zone-B General, Zone-C General). Seed data: 16 products, 5 existing orders. 3 scenarios: standard-fulfillment, supplier-delay, rush-order. All 10 ADRs preserved unchanged.
- **Design doc:** `.squad/decisions/inbox/maverick-supply-chain-domain-model.md` (archived)

### DOMAIN-P3-002: Supply Chain Agent Roster

- **Author:** Maverick | **Date:** 2026-04-02 | **Status:** ~~Implementing~~ SUPERSEDED by DOMAIN-C-002
- 6 agents → 6 agents, 1:1 mapping. bed-coordinator→supply-coordinator, predictive-capacity→demand-forecaster, bed-allocation→inventory-allocator, evs-tasking→warehouse-ops, transport-ops→logistics-planner, policy-safety→compliance-monitor. Same supervisor pattern (ADR-004). Per-agent tool sets defined. Prompt files renamed accordingly.
- **Design doc:** `.squad/decisions/inbox/maverick-supply-chain-agent-roster.md` (archived)

### PLAN-P3-001: Phase 3 Work Item Decomposition — 17 WIs

- **Author:** Maverick | **Date:** 2026-04-02 | **Status:** ~~In Progress~~ SUPERSEDED by PLAN-C-001
- 17 WIs: Goose 9 (WI-P3-001 through WI-P3-009, critical path), Viper 4 (WI-P3-011 through WI-P3-014), Iceman 2 (WI-P3-016, WI-P3-017), Jester 2 (WI-P3-010, WI-P3-015). Critical path: enums→entities→transitions→store→tools→schemas→prompts→orchestrator→scenarios→tests. UI parallelizable after store stabilizes.
- **Design doc:** `.squad/decisions/inbox/maverick-phase3-work-items.md` (archived)

### DOMAIN-C-001: Supply Closet Replenishment — Domain Model

- **Author:** Maverick | **Date:** 2026-04-02 | **Status:** Implementing
- **Supersedes:** DOMAIN-P3-001 (fulfillment center model)
- Full domain pivot from distribution/fulfillment center → hospital supply closet replenishment. Target audience: hospital supply chain directors. Core workflow: Scan → Analyze → Source → Order → Approve → Fulfill. 8 entities: SupplyCloset, SupplyItem, Vendor, CatalogEntry, PurchaseOrder, POLineItem, ScanResult, Shipment. 9 enums: ItemCategory (8 values), ItemCriticality (3), ContractTier (3), POState (8), POApprovalStatus (4), ScanState (7), VendorStockStatus (4), ShipmentState (5), plus TaskState/IntentTag unchanged. Seed data: 1 closet (CLOSET-3N), 15 supply items with par levels, 3 vendors (MedLine, Cardinal, McKesson), 15 catalog entries. 2 scenarios: routine-restock, critical-shortage. All 10 ADRs preserved unchanged.
- **Design doc:** `.squad/decisions/inbox/maverick-closet-domain-model.md`

### DOMAIN-C-002: Supply Closet Replenishment — Agent Roster (5 Agents)

- **Author:** Maverick | **Date:** 2026-04-02 | **Status:** Implementing
- **Supersedes:** DOMAIN-P3-002 (fulfillment center agent roster)
- 6 agents → 5 agents. supply-coordinator (supervisor), supply-scanner (vision/detection), catalog-sourcer (vendor lookup), order-manager (PO creation), compliance-gate (approval/policy). Logistics-planner removed — shipping merged into order-manager. Same supervisor pattern (ADR-004). 13 tools across 5 agents. Compliance gate: $1,000 auto-approval threshold, human-in-the-loop for POs exceeding threshold (NEW concept).
- **Design doc:** `.squad/decisions/inbox/maverick-closet-agent-roster.md`

### PLAN-C-001: Supply Closet Work Item Decomposition — 20 WIs

- **Author:** Maverick | **Date:** 2026-04-02 | **Status:** Complete — all 20 WIs verified
- **Supersedes:** PLAN-P3-001 (fulfillment center 17 WIs)
- 20 WIs: Goose 11 (WI-C-001 through WI-C-011, critical path), Viper 5 (WI-C-013 through WI-C-017), Jester 2 (WI-C-012, WI-C-018), Iceman 2 (WI-C-019, WI-C-020). Critical path: enums→entities+events+transitions→store→tools+routers→schemas+prompts→orchestrator→scenarios→tests. UI parallelizable after store stabilizes. 3 new WIs for human-in-the-loop UI components (VendorChoiceCard, HumanApprovalCard).
- **Design doc:** `.squad/decisions/inbox/maverick-closet-work-items.md`

### IMPL-C-001: Foundation Layer — Models Rewrite (WI-C-001 through WI-C-004)

- **Author:** Goose | **Date:** 2026-04-02 | **Status:** Complete
- Rewriting enums.py, entities.py, events.py, transitions.py for closet domain. Previous fulfillment center types (Order, Product, OrderState, ProductState, FulfillmentPriority, SourceChannel) being replaced with closet types (PurchaseOrder, SupplyItem, POState, ScanState, ItemCategory, ItemCriticality, ContractTier). State store rewrite (WI-C-005) follows after models layer lands.

### IMPL-C-002: State Store Rewrite Context

- **Author:** Goose | **Date:** 2026-04-02 | **Status:** Complete
- Previous supply chain state store (SUPPLY_CHAIN_CONFIG, 16 products, 5 orders, 2 warehouses) will be replaced by closet state store (CLOSET_CONFIG, 15 supply items, 1 closet, 3 vendors, 15 catalog entries). Downstream consumers (orchestrator, tool_functions, routers/state) will break at import until updated.

### TEST-C-001: Test Infrastructure Prep

- **Author:** Jester | **Date:** 2026-04-02 | **Status:** Complete
- Updated conftest.py, test_models.py, test_transitions.py to use closet domain entities and enums. Tests will fail on import until Goose lands WI-C-001 + WI-C-002. Estimated ~245 tests across both files once runnable.

### IMPL-C-003: Closet Foundation Layer Complete

- **Author:** Goose | **Date:** 2026-04-02 | **Status:** Complete
- Rewrote all 5 model files (enums.py, entities.py, events.py, transitions.py, **init**.py) to the hospital supply closet replenishment domain per Maverick's design spec. Same architecture (all ADRs hold), new nouns.

### INFRA-C-001: Stale Reference Cleanup — Infrastructure, Docs, Scripts

- **Author:** Goose | **Date:** 2026-04-02 | **Status:** Complete
- Fixed 14 stale bed-management references across azure.yaml, squad.config.ts, infra/, docs/, and scripts/. All references now use supply-closet/supply-chain naming.

### STATUS-C-001: Supply Closet Pivot Complete

- **Author:** Squad Coordinator | **Date:** 2026-04-02 | **Status:** Verified
- Full domain pivot from bed management to supply closet replenishment is complete. 505 backend tests passing, 20 frontend tests passing, TypeScript compiles clean. All stale bed-management references cleaned up across infrastructure (azure.yaml, Bicep, main.json), documentation (architecture.md, azure-deployment.md, local-development.md), scripts (build_agents.py), and frontend (package.json, CommandCenter.tsx, test data). 5 agents operational: supply-coordinator, supply-scanner, catalog-sourcer, order-manager, compliance-gate. Both scenarios (routine-restock, critical-shortage) fully implemented in simulated mode.

### VISION-001: Two-Phase Image Scan API Design

- **Author:** Goose | **Date:** 2026-04-07 | **Status:** Implemented
- Added `POST /api/scenario/scan-image` (filename → closet detection + inventory) and `POST /api/scenario/start-workflow` (closet_id + scenario_type → orchestration). New router at `src/api/app/routers/vision.py`. Two-phase design lets UI show detected inventory before user confirms workflow start. Vision router has its own `_scenario_lock` (not shared with scenarios.py) — acceptable for demo single-user sequential interactions.

### UI-003: Three-Phase Demo Flow (Upload → Analysis → Dashboard)

- **Author:** Viper | **Date:** 2026-04-07 | **Status:** Implemented
- ControlTower refactored to `DemoPhase` state machine: upload (ImageUpload.tsx drag-drop), analysis (VisionAnalysis.tsx scanning animation + progressive item reveal), dashboard (existing). ScenarioToolbar shows "New Scan" button + closet thumbnail in dashboard phase. 422 error handling for unrecognized closet images.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
