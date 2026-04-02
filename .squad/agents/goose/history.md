# Project Context

- **Owner:** acworkma
- **Project:** Patient Flow / Bed Management — Agentic AI Demo (Azure + Foundry + ACA)
- **Stack:** Python/FastAPI backend, React/Tailwind/shadcn frontend, Azure Container Apps, Azure AI Foundry, Bicep/azd infra
- **Created:** 2026-03-07

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-07: WI-002 + WI-003 — Domain Model & Event System
- Implemented full domain model in `src/api/app/models/`: enums, entities (Pydantic v2), transitions (state machine validation), events
- Enums use `StrEnum` for JSON-friendly string serialization
- All six entities (Bed, Patient, Task, Transport, Reservation, AgentMessage) are Pydantic BaseModel with proper defaults and validators
- `InvalidTransitionError` carries entity_type, current, target for debuggable messages
- Bed transitions include Any→BLOCKED and BLOCKED→DIRTY per spec
- EventStore: append-only, monotonic sequence, asyncio.Lock, subscriber queues for SSE
- StateStore: in-memory dicts, asyncio.Lock on mutations, `validate_transition()` enforced on every state change
- Seed data: 12 beds across 4-North and 5-South units, 4 existing patients in ARRIVED state
- Snapshot method uses `model_dump(mode="json")` for datetime serialization
- Key file paths: `src/api/app/models/`, `src/api/app/events/event_store.py`, `src/api/app/state/store.py`

### 2026-03-07: WI-007 + WI-008 + WI-009 — API Endpoints, Tool Functions, Agent Build
- **MessageStore** (`src/api/app/messages/message_store.py`): mirrors EventStore pattern — publish, get_messages (index-based), subscribe/unsubscribe SSE queues. Singleton in `messages/__init__.py`.
- **Messages router** (`src/api/app/routers/messages.py`): wired to MessageStore with SSE streaming via subscriber queue, supports `?since=` index filter.
- **Scenarios router** (`src/api/app/routers/scenarios.py`): `POST /api/scenario/seed` resets+seeds state; happy-path creates an incoming patient + PatientBedRequestCreated event; disruption-replan blocks a READY bed to reduce capacity.
- **App lifespan** seeds initial state on startup.
- **Tool functions** (`src/api/app/tools/tool_functions.py`): 10 tools — `get_patient`, `get_beds`, `get_tasks`, `reserve_bed`, `release_bed_reservation`, `create_task`, `update_task`, `schedule_transport`, `publish_event`, `escalate`. Each validates inputs, mutates state via StateStore transitions, emits events, publishes agent messages.
- **Tool schemas** (`src/api/app/tools/tool_schemas.py`): OpenAI function-calling format schemas; per-agent tool sets mapping in `AGENT_TOOLS` dict for 6 agents.
- **Agent prompts** (`src/api/app/agents/prompts/*.txt`): 6 prompt files — flow-coordinator, predictive-capacity, bed-allocation, evs-tasking, transport-ops, policy-safety. Each includes role, responsibilities, decision framework, communication style, and available tools.
- **build_agents.py** (`scripts/build_agents.py`): supports both PROJECT_ENDPOINT (preferred) and PROJECT_CONNECTION_STRING (fallback); reads prompts from txt files; loads tool schemas from app module; idempotent create/update via list→match→create/update pattern; outputs JSON agent ID map.
- All 221 existing tests still pass; no regressions.

### 2026-03-09: WI-029 — Conciseness constraints added to agent prompts
- Appended `## Output Format` section to all 6 prompt files in `src/api/app/agents/prompts/`.
- Each section constrains response length and format: flow-coordinator (2-3 sentence updates, 100-word summaries), predictive-capacity (structured list, 2-sentence reasoning), bed-allocation (1-2 sentence results), evs-tasking (1-sentence confirmation), transport-ops (1-sentence confirmation), policy-safety (PASS/FAIL first line + 1-2 sentence reasoning).
- No existing content modified — append-only change to prompt files.
- All 9 existing tests pass; no regressions.

### 2026-03-09: WI-024 — Per-Agent Latency and Token Tracking
- Added `AgentMetrics` and `ScenarioMetrics` TypedDicts to `src/api/app/agents/orchestrator.py`
- Instrumented `_invoke_agent` (nested in `_run_live`) with `time.monotonic()` wall-clock timers, `response.usage` token extraction, and round counting across multi-round tool-call loops
- `_invoke_agent` now returns `{"text": str, "metrics": AgentMetrics}` instead of bare string; all callers in `_run_live` updated to destructure result
- `_run_live` collects per-agent metrics list, computes scenario totals (`total_latency_seconds`, `total_input_tokens`, `total_output_tokens`), and returns `ScenarioMetrics` under `"metrics"` key
- `_simulate_happy_path` and `_simulate_disruption_replan` return zero-token metrics with `time.monotonic()` latency tracking; `"mode": "simulated"` added to return dicts
- Structured logging added: `logger.info("agent=%s model=%s input_tokens=%d output_tokens=%d rounds=%d latency_s=%.2f", ...)`
- Used `getattr(response, "usage", None)` for safe access to response.usage (defensive against SDK variations)
- All 344 existing tests pass; no regressions
- Key file: `src/api/app/agents/orchestrator.py` (sole file changed)

### 2026-03-09: WI-025 — Expose metrics via /api/metrics endpoint
- Created `src/api/app/metrics/metrics_store.py`: in-memory store with asyncio.Lock, `record()`, `get_latest()`, `get_history(limit)`, `clear()` — mirrors EventStore/StateStore pattern
- Created `src/api/app/routers/metrics.py`: `GET /api/metrics` (latest run) and `GET /api/metrics/history?limit=N` (last N runs, most recent first); returns `{"message": "No scenario runs recorded yet"}` with 200 when empty
- Registered metrics router in `src/api/app/main.py` following existing pattern
- Updated `src/api/app/routers/scenarios.py`: both happy-path and disruption-replan background tasks now call `metrics_store.record(result["metrics"])` after orchestration completes
- Added `MetricsStore` fixture and singleton clearing in `src/api/tests/conftest.py`
- Created `src/api/tests/test_metrics.py`: 11 tests covering store unit tests (empty state, record, history ordering, limit, clear) and endpoint tests (empty responses, data after recording, limit param)
- All 355 tests pass; no regressions

### 2026-03-09: WI-026 — Per-agent model configuration with AGENT_MODEL_OVERRIDES
- Added `AGENT_MODEL_OVERRIDES: str = "{}"` to `src/api/app/config.py` Settings class — JSON string env var, parsed at usage time
- Updated `_run_live` in `src/api/app/agents/orchestrator.py`: parses `AGENT_MODEL_OVERRIDES` once into `_model_overrides` dict; `_invoke_agent` resolves model per agent via `_model_overrides.get(agent_name) or default_deployment`; resolved model set in `AgentMetrics` correctly
- Updated `scripts/build_agents.py`: reads `AGENT_MODEL_OVERRIDES` env var, resolves per-agent model when building Foundry agent definitions via `model_overrides.get(agent_name) or model_deployment`
- Pattern: env var is a JSON string, defensive `json.loads` with try/except fallback to empty dict — consistent with existing `AGENT_MAX_TOKENS_OVERRIDES` pattern
- All 355 tests pass; no regressions

### 2026-03-09: WI-028 — Add max_output_tokens to Responses API calls
- Added `MAX_OUTPUT_TOKENS: int = 1024` and `AGENT_MAX_TOKENS_OVERRIDES: str = "{}"` to `src/api/app/config.py` Settings
- `AGENT_MAX_TOKENS_OVERRIDES` is a JSON string env var for per-agent overrides (e.g. `'{"flow-coordinator":2048}"`); parsed once in `_run_live` with a `json.loads` + fallback on decode error
- Resolved token limit per agent: `override_dict.get(agent_name) or settings.MAX_OUTPUT_TOKENS`
- Passed `max_output_tokens=resolved_value` to **both** `responses.create()` calls in `_invoke_agent` (initial and tool-result follow-ups)
- Added `max_output_tokens` field to `AgentMetrics` TypedDict and populated it in the metrics dict
- Truncation handling: check `response.status == "incomplete"` after each API call; log a warning and break out of tool-call loop on truncation (don't crash)
- All 355 tests pass; no regressions
- Key files changed: `src/api/app/config.py`, `src/api/app/agents/orchestrator.py`

### 2026-03-10: Runtime Model Config Endpoint (GET/PUT /api/config)
- Created `src/api/app/config_store.py`: `RuntimeConfigStore` singleton with asyncio.Lock — mutable overlay on top of env var settings. Pattern mirrors EventStore/MetricsStore. Fields: `model_deployment`, `agent_model_overrides`, `max_output_tokens`, `agent_max_tokens_overrides`. Read via `get_config()` (no lock needed for reads), mutate via `update_config()` / `reset()`.
- Created `src/api/app/routers/config.py`: `GET /api/config` (current effective config), `PUT /api/config` (partial update via Pydantic model), `POST /api/config/reset` (revert to env var defaults)
- Updated `src/api/app/agents/orchestrator.py`: `_run_live` now reads from `runtime_config.get_config()` instead of parsing `settings.AGENT_MODEL_OVERRIDES` / `settings.AGENT_MAX_TOKENS_OVERRIDES` directly. Falls back to env var defaults when no runtime override is set.
- Registered config router in `src/api/app/main.py`
- Created `src/api/tests/test_config_endpoint.py`: 17 tests — 8 unit tests for the store, 9 endpoint integration tests. All 372 tests pass.
- Pattern: runtime config is a transparent overlay — orchestrator doesn't need to know whether a value came from env vars or a PUT call. The `_parse_json` helper is shared.

### 2026-04-02: WI-P3-001 + WI-P3-002 — Supply Chain Domain Model Rewrite (Enums, Entities, Events, Transitions)
- Rewrote 5 files in `src/api/app/models/`: `enums.py`, `entities.py`, `events.py`, `transitions.py`, `__init__.py`
- **Enums replaced:** `BedState` → `ProductState`, `PatientState` → `OrderState`, `TransportPriority` → `FulfillmentPriority`, `AdmissionSource` → `SourceChannel`. Added `ShipmentState` (new). `TaskState` and `IntentTag` kept as-is. `TaskType` values changed from EVS_CLEANING/TRANSPORT/BED_PREP to PICK/PACK/QUALITY_CHECK/RESTOCK.
- **Entities replaced:** `Bed` → `Product` (with warehouse, quantity, reorder fields), `Patient` → `Order` (with nested `OrderItem` model), `Transport` → `Shipment` (with carrier, tracking_number, ShipmentState), `Reservation` → `Allocation` (quantity-based). `Task` retained same shape but uses new `FulfillmentPriority` and `TaskType`. `AgentMessage` unchanged.
- **Events replaced:** 15 event constants renamed 1:1 from bed-management to supply-chain (e.g., `PATIENT_BED_REQUEST_CREATED` → `ORDER_CREATED`, `BED_RESERVED` → `INVENTORY_ALLOCATED`). `Event` and `StateDiff` models unchanged.
- **Transitions replaced:** `VALID_BED_TRANSITIONS` → `VALID_PRODUCT_TRANSITIONS`, `VALID_PATIENT_TRANSITIONS` → `VALID_ORDER_TRANSITIONS`, added `VALID_SHIPMENT_TRANSITIONS`. `VALID_TASK_TRANSITIONS` kept as-is. `validate_transition()` updated to detect `OrderState`, `ProductState`, `ShipmentState` in addition to `TaskState`.
- **Patterns preserved:** `StrEnum` for all enums, Pydantic v2 `BaseModel` with `Field`, `_utcnow` helper, `Optional[str]` for nullable fields, `InvalidTransitionError` with entity_type/current/target.
- All imports verified clean via `python3 -c "from src.api.app.models import *"`.
- **Downstream breakage expected:** `state/store.py`, `tools/tool_functions.py`, `tools/tool_schemas.py`, `routers/*.py`, `agents/orchestrator.py`, and all tests reference the old names. They need updating in follow-up work items.
- **Coordinated rename** across full stack. Goose handled backend: `orchestrator.py` (`_simulate_happy_path` → `_simulate_er_admission`), `scenarios.py` (route + function), `test_endpoints.py` and `test_scenarios.py` (classes, URLs, assertions). Viper updated frontend `ScenarioToolbar.tsx`. Jester updated tests + `smoke_test.sh`. Maverick updated docs, eval scripts, and eval result JSON files. All 391 tests pass.

### 2026-03-09: WI-030 — Build model comparison evaluation script
- Created `scripts/model_eval.py`: stdlib-only CLI (argparse, json, urllib.request, time, glob, statistics) for running scenarios and comparing results across models
- Two modes: **run mode** (`--model gpt-5.2 --runs 3`) seeds state, triggers scenario, polls `/api/metrics/history` for new entries, collects per-agent metrics across N runs; **compare mode** (`--compare eval-results-*.json`) reads multiple result files and prints summary + per-agent breakdown tables
- Polling logic: records pre-trigger history length, polls with exponential backoff (2s→5s cap) until a new entry appears or 300s timeout

### 2026-04-02: WI-C-001 through WI-C-004 — Supply Closet Replenishment Domain Model (Foundation Layer)
- Second full domain pivot: supply-chain fulfillment center → hospital supply closet replenishment
- Rewrote 5 files in `src/api/app/models/`: `enums.py`, `entities.py`, `events.py`, `transitions.py`, `__init__.py`
- **Enums:** Removed OrderState, ProductState, TaskType, FulfillmentPriority, SourceChannel. Kept TaskState, IntentTag. Rewrote ShipmentState (simplified 5-state: CREATED→SHIPPED→IN_TRANSIT→DELIVERED, with DELAYED). Added 7 new enums: ItemCategory, ItemCriticality, ContractTier, POState, POApprovalStatus, ScanState, VendorStockStatus.
- **Entities:** Removed Order, OrderItem, Product, Task, Shipment (old), Allocation. Added SupplyCloset, SupplyItem, Vendor, CatalogEntry, PurchaseOrder, POLineItem, ScanResult, ReorderItem, Shipment (simplified). Kept AgentMessage unchanged.
- **Events:** Replaced 15 supply-chain events with 17 closet workflow events across 5 categories: scan lifecycle (3), sourcing (3), purchase orders (7), fulfillment (3), escalation (1). Kept StateDiff and Event models unchanged.
- **Transitions:** Removed VALID_ORDER_TRANSITIONS, VALID_PRODUCT_TRANSITIONS. Added VALID_SCAN_TRANSITIONS (7-state), VALID_PO_TRANSITIONS (8-state). Rewrote VALID_SHIPMENT_TRANSITIONS (5-state). Kept VALID_TASK_TRANSITIONS. Updated validate_transition() to handle ScanState and POState.
- **Patterns preserved:** StrEnum for all enums, Pydantic v2 BaseModel with Field, _utcnow() helper, Optional[str] for nullable fields, InvalidTransitionError with entity_type/current/target.
- All imports verified clean via `python3 -c "from src.api.app.models import *"`.
- **Downstream breakage expected:** state/store.py, tools/*, routers/*, agents/orchestrator.py, and all tests reference old names. Follow-up work items needed.
- JSON output format: `model`, `scenario`, `runs`, `timestamp`, `summary` (avg latency/tokens/rounds), `per_agent` (per-agent averages), `raw_runs` (full metrics from each run)
- Comparison table format: aligned columns with comma-separated numbers; per-agent breakdown printed per model
- Uses only stdlib — no external dependencies; executable with `#!/usr/bin/env python3`
- Key file: `scripts/model_eval.py`

### 2026-04-02: Cross-agent note from Scribe (Phase 3 kickoff)
- **Phase 3 supply chain pivot initiated.** Maverick designed full domain model — see decisions.md DOMAIN-P3-001, DOMAIN-P3-002, PLAN-P3-001.
- Goose assigned WI-P3-001 through WI-P3-009 (critical path). Viper working TypeScript types + UI (WI-P3-011). Jester has test fixtures ready and waiting for domain code to land.
- All 10 ADRs unchanged. Architecture stays — only domain nouns change.

### 2026-04-02: WI-P3-003 — State Store Rewrite (Supply Chain)
- Full rewrite of `src/api/app/state/store.py`: replaced all hospital/bed-management domain with supply-chain domain
- **Config:** `HOSPITAL_CONFIG` → `SUPPLY_CHAIN_CONFIG` with 3 warehouses (east-dc, west-dc, central-dc), zone lists, cold_chain flags
- **Helpers:** `get_unit_for_diagnosis` → `get_warehouse_for_product(product_id, store)`, `get_campus_for_unit` → `get_warehouses_with_cold_chain()`
- **StateStore collections:** `beds/patients/transports/reservations` → `products/orders/shipments/allocations`. `tasks` unchanged.
- **Getters:** 1:1 mapping with same `Optional[Callable]` filter pattern preserved. `get_active_reservations` → `get_active_allocations`.
- **Transitions:** `transition_bed` → `transition_product` (ProductState, VALID_PRODUCT_TRANSITIONS), `transition_patient` → `transition_order` (OrderState, VALID_ORDER_TRANSITIONS), `transition_transport` → `transition_shipment` (ShipmentState, VALID_SHIPMENT_TRANSITIONS). `transition_task` unchanged.
- **Seed data:** 16 products across 3 warehouses (Electronics, Home & Garden, Cold Chain, General Merchandise); realistic state mix (AVAILABLE, LOW_STOCK, OUT_OF_STOCK, ON_HOLD). 5 orders (DELIVERED, SHIPPED, ALLOCATED, VALIDATED, PENDING) with OrderItem lists. Product IDs like `PROD-TV55-EA`, Order IDs like `ORD-EXIST-01`.
- **`__init__.py` updated:** exports `get_warehouse_for_product` and `get_warehouses_with_cold_chain` instead of old helpers.
- **Downstream breakage:** `orchestrator.py` (imports `get_campus_for_unit`, `HOSPITAL_CONFIG`), `tool_functions.py` (imports `get_unit_for_diagnosis`, `get_campus_for_unit`), `routers/state.py` (imports `HOSPITAL_CONFIG`). These need updates in WI-P3-004+.

### 2026-04-02: WI-P3-004 + WI-P3-005 — Tool Functions + Tool Schemas Rewrite (Supply Chain)
- Full rewrite of `src/api/app/tools/tool_functions.py`: 10 functions replacing all hospital/bed-management tools
- **Read-only tools (3):** `get_patient` → `get_order`, `get_beds` → `get_products` (filters: warehouse_id, state, category), `get_tasks` unchanged (same filter pattern)
- **Mutation tools (7):** `reserve_bed` → `allocate_inventory` (quantity-based with net-available check, auto-transitions product state to ALLOCATED or LOW_STOCK), `release_bed_reservation` → `release_allocation` (deactivates allocation, decrements quantity_allocated, auto-transitions state back), `create_task` updated (FulfillmentPriority, WAREHOUSE_TASK_CREATED event, "warehouse-ops" agent), `update_task` updated (TASK_STATUS_CHANGED event, "warehouse-ops" agent), `schedule_transport` → `schedule_shipment` (order-based, auto-carrier selection by CARRIER_BY_PRIORITY dict, TRK-prefix tracking numbers), `publish_event` unchanged, `escalate` updated ("compliance-monitor" agent)
- **Key patterns:** All mutation tools follow validate→mutate→emit→message→return. `**_kwargs` on read-only tools for forward compat. Auto state transitions wrapped in try/except to handle invalid transitions gracefully.
- Full rewrite of `src/api/app/tools/tool_schemas.py`: 10 OpenAI function-calling schemas with updated enums
- **Per-agent tool sets:** 6 agents mapped: supply-coordinator, demand-forecaster, inventory-allocator, warehouse-ops, logistics-planner, compliance-monitor. AGENT_TOOLS_V2 FunctionTool conversion preserved.
- Updated `src/api/app/tools/__init__.py` with new exports.
- All 10 functions + 10 schemas + 6 agent tool sets + 6 v2 sets import cleanly verified.
- **Downstream breakage remaining:** `orchestrator.py` dispatch table, `routers/scenarios.py`, `routers/state.py`, and all tests still reference old function/schema names.
