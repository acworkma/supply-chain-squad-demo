### 2026-04-02: WI-C-001 through WI-C-004 — Closet Foundation Layer Complete

**By:** Goose (Backend Dev)
**What:** Rewrote all 5 model files (`enums.py`, `entities.py`, `events.py`, `transitions.py`, `__init__.py`) to the hospital supply closet replenishment domain per Maverick's design spec.
**Why:** Domain pivot from fulfillment center to hospital supply closet. Same architecture (all ADRs hold), new nouns.
**Impact:** All downstream files (`state/store.py`, `tools/*`, `routers/*`, `agents/orchestrator.py`, tests) still reference old names and will break until updated. This is the foundation layer — everything above depends on it.
