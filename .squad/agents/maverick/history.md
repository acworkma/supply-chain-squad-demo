# Project Context

- **Owner:** acworkma
- **Project:** Patient Flow / Bed Management — Agentic AI Demo (Azure + Foundry + ACA)
- **Stack:** Python/FastAPI backend, React/Tailwind/shadcn frontend, Azure Container Apps, Azure AI Foundry, Bicep/azd infra
- **Created:** 2026-03-07

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-07 — Spec Decomposition & Architecture Decisions

**Architecture decisions made (10 ADRs):**
- ADR-001: In-memory state store, no database (demo scope)
- ADR-002: Event sourcing lite — dual-write state + events, not full replay
- ADR-003: Tool-backed state mutation — agents never mutate directly (core invariant)
- ADR-004: Supervisor orchestration — Flow Coordinator routes to specialists
- ADR-005: Single container deployment (FastAPI serves static React build)
- ADR-006: SSE for real-time UI updates (not WebSockets)
- ADR-007: Scenario reset on trigger — clean slate each run, async execution
- ADR-008: Agent prompts as files in `src/api/agents/prompts/`, tools from Python type annotations
- ADR-009: Chat transcript model with intent tags (PROPOSE/VALIDATE/EXECUTE/ESCALATE)
- ADR-010: Predictive capacity uses simulated confidence scores, not real ML

**Key file paths:**
- Decomposition: `.squad/decisions/inbox/maverick-spec-decomposition.md`
- Architecture decisions: `.squad/decisions/inbox/maverick-architecture-decisions.md`

**Work distribution:** 23 WIs across 4 phases. Goose carries heaviest load (9 WIs — domain model through scenarios). Viper has 6 WIs (UI shell through polish). Iceman has 3 WIs (infra + deploy + CI/CD). Jester has 4 WIs (test framework through smoke tests). Maverick owns WI-001 (scaffolding) + ongoing code review.

**Key insight:** The critical path runs through WI-001 (scaffold) → WI-002/003 (domain+events) → WI-007/008 (API+tools) → WI-014 (orchestration) → WI-015/016 (scenarios). Goose is on the critical path for most of the project. Frontend and infra are parallelizable off the critical path.

### 2026-03-07 — WI-001 Repo Scaffolding Complete

**Created/verified the canonical repo layout. Key structural facts:**
- Python API: `src/api/` — FastAPI app at `app.main:app`, routes under `/api/*`, static mount at `/` for production
- Singletons: `app.state.store` (StateStore) and `app.events.event_store` (EventStore) exported from package `__init__.py`
- Routers: state, events, messages, scenarios — all under `/api` prefix. Events has SSE stream via queue-based subscription.
- Models already enriched by Goose: includes state transitions (`transitions.py`), `AgentMessage`, `TaskType`, `TransportPriority` beyond original spec
- UI: React + Vite + Tailwind with `ControlTower` layout component, all pane components already scaffolded (BedBoard, PatientQueue, TransportQueue, AgentConversation, EventTimeline)
- Infra: Complete Bicep modules (foundry, aca, observability) + main orchestrator + azd config
- Dockerfile: Multi-stage Node→Python build, UI dist copied to `./static`
- Scripts: `build_agents.py` (skeleton), `smoke_test.sh` (curl health check)
- Agent prompts directory: `src/api/app/agents/prompts/` (empty, ready for WI-009)
- Tests already set up by Jester: pytest + vitest with real test files

**Acceptance criteria verified:**
1. ✅ `cd src/api && pip install -e .` — installs cleanly
2. ✅ UI has package.json with dev script, npm install/dev would work
3. ✅ All Python files importable — enums, entities, events, config, state, event_store, all routers, main app
4. ✅ Directory structure matches spec §15

### 2026-03-27 — Cross-team rename — Happy Path → ER Admission (docs/eval)
- Updated README.md, docs/architecture.md, docs/local-development.md, docs/azure-deployment.md, scripts/model_eval.py, and 3 eval-results JSON files. Coordinated with Goose (backend code), Viper (frontend), Jester (tests + smoke_test.sh). Full-stack rename complete; 391 tests pass.

### 2026-03-09 — Full 23-WI Codebase Audit Complete

**All 4 phases verified against actual code. Every work item confirmed implemented.**

- 344 backend tests passing (pytest). Frontend TypeScript compiles clean (vitest + tsc).
- Both orchestration modes working: live Azure AI Foundry and simulated/local fallback.
- CI pipeline (GitHub Actions) runs tests + build on push/PR.
- Smoke test script (`scripts/smoke_test.sh`) covers health, state, events, and full scenario execution.
- All 10 original ADRs moved from PROPOSED → Implemented in `decisions.md`. PLAN-001 marked complete.
- Architecture held up exactly as designed on day one. No ADR was violated or needed revision. The tool-backed mutation boundary (ADR-003) proved its worth — every state change flows through tool functions, making the system fully auditable.
- Key file sizes: orchestrator.py (947 lines), tool_functions.py (10 tools), 6 prompt files, full Bicep infra.
- Decision inbox entry written: `.squad/decisions/inbox/maverick-all-phases-complete.md`
