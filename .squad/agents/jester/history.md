# Project Context

- **Owner:** acworkma
- **Project:** Patient Flow / Bed Management — Agentic AI Demo (Azure + Foundry + ACA)
- **Stack:** Python/FastAPI backend, React/Tailwind/shadcn frontend, Azure Container Apps, Azure AI Foundry, Bicep/azd infra
- **Created:** 2026-03-07

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-07: Cross-agent note from Scribe (decision merge)
- Goose implemented tools as standalone async functions with `state_store`, `event_store`, `message_store` as kwargs (ADR-003a). This means tests can pass mock stores directly — no service class instantiation needed. Leverage this pattern for WI-018 domain model & API tests.

### 2026-03-07: WI-018 — Domain Model + API Endpoint Tests (Phase 2)
- **Test suite: 318 tests, 0 failures.** Breakdown: transitions (106), models (64), tool_functions (53), state_store (50), endpoints (27), event_store (18).
- **Key test files:**
  - `src/api/tests/conftest.py` — fixtures for fresh state_store, event_store, message_store per test; test_client resets singleton stores
  - `src/api/tests/test_models.py` — entity creation, defaults, serialization, enum completeness (Phase 1 — unchanged)
  - `src/api/tests/test_transitions.py` — exhaustive valid+invalid parametrized transitions for bed/patient/task (Phase 1 — unchanged)
  - `src/api/tests/test_state_store.py` — seeding, snapshots, getters, transitions, concurrent access, unit distribution (expanded)
  - `src/api/tests/test_event_store.py` — publish, retrieval, filtering, clear, subscribe/unsubscribe (Phase 1 — unchanged)
  - `src/api/tests/test_tool_functions.py` — all 10 tool functions tested: get_patient, get_beds, get_tasks, reserve_bed, release_bed_reservation, create_task, update_task, schedule_transport, publish_event, escalate (**NEW**)
  - `src/api/tests/test_endpoints.py` — health, state, events, messages, seed, happy-path, disruption-replan (**NEW**)
- **Pattern confirmed:** ADR-003a kwargs pattern makes tool testing trivial — pass fresh stores directly, no mocks needed.
- **Test client approach:** httpx AsyncClient + ASGITransport wraps FastAPI app. Singleton stores must be cleared in fixture since routers import global singletons.
- **Gotcha:** ASGI lifespan handling in httpx ASGITransport can produce surprising state interactions — patient state assertions after scenario seeds may not match expectations. Verify via events/existence instead of exact state checks.
- **Run command:** `cd src/api && python -m pytest tests/ -v` (tests live in `src/api/tests/`, not top-level `tests/api/`).

### 2026-03-27: Cross-team rename — happy-path → er-admission (tests)
- Updated `test_scenarios.py`, `test_endpoints.py`: renamed test classes (`TestHappyPathEndpoint` → `TestERAdmissionEndpoint`, `TestHappyPathE2E` → `TestERAdmissionE2E`), method names, URLs, assertions, comments. Updated `scripts/smoke_test.sh` route references. Coordinated with Goose (backend), Viper (frontend), Maverick (docs).

### 2026-03-09: Collapsible Agent Message Tests (AgentConversation)
- **Test file:** `src/ui/src/test/AgentConversation.test.tsx` — 9 tests, all passing.
- **Coverage:** empty state, short msg (no toggle), long msg summary, multiline summary, expand click, collapse click, independent expand tracking across messages, event ID chips present/absent.
- **jsdom gotcha:** `Element.prototype.scrollIntoView` must be stubbed — jsdom doesn't implement it, and the component's auto-scroll effect crashes without it.
- **CSS-hidden content in jsdom:** The collapsible grid (`grid-rows-[0fr]` + `overflow-hidden`) keeps full content in the DOM even when collapsed. Don't assert hidden via `queryByText` returning null — instead check the chevron's `rotate-90` class and the summary span's text content to distinguish collapsed vs expanded state.
- **Run command:** `cd src/ui && npx vitest run src/test/AgentConversation.test.tsx`

### 2026-04-02: WI-P3-010 PREP — Supply Chain Test Fixtures & Model/Transition Tests
- **Files updated:** `conftest.py`, `test_models.py`, `test_transitions.py`
- **conftest.py:** Replaced all bed-management fixtures with supply chain equivalents. 16 products across 3 zones (Zone-A/east-dc electronics, Zone-B/east-dc general merchandise, Zone-C/west-dc general), 5 orders at ALLOCATED/PICKING/PACKED/SHIPPED/VALIDATED states, 3 tasks (PICK/PACK/QUALITY_CHECK), 2 shipments (IN_TRANSIT/CREATED), 2 allocations. Store fixtures + test_client unchanged.
- **test_models.py:** 8 enum completeness classes (OrderState×9, ProductState×6, ShipmentState×7, TaskState×6, TaskType×5, FulfillmentPriority×3, SourceChannel×4, IntentTag×4). 6 entity creation classes (Product, Order, OrderItem, Task, Shipment, Allocation) + AgentMessage (unchanged). 4 serialization classes (Product, Order, Shipment, Task). Estimated ~75 tests.
- **test_transitions.py:** 4 state machines — Order (13 valid / 59 invalid), Product (17 valid / 13 invalid), Shipment (10 valid / 32 invalid), Task (7 valid / 23 invalid, unchanged). Parametrized exhaustive valid+invalid tests + semantic tests (terminal states, entry points, CANCELLED reachability, ON_HOLD reachability, DELAYED reachability, BACKORDERED→ALLOCATED). Estimated ~170 tests.
- **Pattern:** Same pytest parametrize + exhaustive coverage pattern from Phase 2. Every valid transition tested, every invalid transition asserts InvalidTransitionError.
- **Note:** Tests import new entity/enum names that don't exist yet in the codebase. They will fail on import until Goose lands WI-P3-001 (enums+entities) and WI-P3-002 (transitions). This is intentional — tests are READY to validate the domain code as soon as it lands.

### 2026-04-02: Cross-agent note from Scribe (Phase 3 kickoff)
- **Phase 3 supply chain pivot initiated.** Maverick designed full domain model — see decisions.md DOMAIN-P3-001, DOMAIN-P3-002, PLAN-P3-001.
- Jester assigned WI-P3-010 (backend tests) and WI-P3-015 (frontend tests). Test fixtures and model/transition tests already prepped above — waiting for Goose to land domain code.
- Goose on critical path (WI-P3-001 through WI-P3-009). Viper working UI types + components. All 10 ADRs unchanged.
