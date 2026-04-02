"""
API endpoint tests — FastAPI routes via httpx AsyncClient.

Uses the test_client fixture which resets singleton stores between tests.
"""

import pytest

from httpx import AsyncClient


# ===================================================================
# GET /health
# ===================================================================

class TestHealthEndpoint:

    async def test_health_returns_200(self, test_client: AsyncClient):
        resp = await test_client.get("/health")
        assert resp.status_code == 200

    async def test_health_returns_ok_status(self, test_client: AsyncClient):
        resp = await test_client.get("/health")
        assert resp.json()["status"] == "ok"


# ===================================================================
# GET /api/state
# ===================================================================

class TestStateEndpoint:

    async def test_state_returns_200(self, test_client: AsyncClient):
        resp = await test_client.get("/api/state")
        assert resp.status_code == 200

    async def test_state_has_expected_keys(self, test_client: AsyncClient):
        resp = await test_client.get("/api/state")
        data = resp.json()
        for key in ("closets", "supply_items", "vendors", "catalog", "scans", "purchase_orders", "shipments"):
            assert key in data, f"Missing key: {key}"

    async def test_state_closets_are_dict(self, test_client: AsyncClient):
        resp = await test_client.get("/api/state")
        assert isinstance(resp.json()["closets"], dict)

    async def test_state_after_seed(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/seed")
        resp = await test_client.get("/api/state")
        data = resp.json()
        assert len(data["closets"]) == 5
        assert len(data["supply_items"]) == 10


# ===================================================================
# GET /api/events
# ===================================================================

class TestEventsEndpoint:

    async def test_events_returns_200(self, test_client: AsyncClient):
        resp = await test_client.get("/api/events")
        assert resp.status_code == 200

    async def test_events_empty_initially(self, test_client: AsyncClient):
        resp = await test_client.get("/api/events")
        assert resp.json() == []

    async def test_events_populated_after_scenario(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/routine-restock")
        resp = await test_client.get("/api/events")
        events = resp.json()
        assert len(events) >= 1

    async def test_events_since_filter(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/routine-restock")
        resp_all = await test_client.get("/api/events")
        all_events = resp_all.json()
        if len(all_events) > 0:
            cutoff = all_events[0]["sequence"]
            resp_filtered = await test_client.get(f"/api/events?since={cutoff}")
            filtered = resp_filtered.json()
            assert all(e["sequence"] > cutoff for e in filtered)


# ===================================================================
# GET /api/agent-messages
# ===================================================================

class TestAgentMessagesEndpoint:

    async def test_messages_returns_200(self, test_client: AsyncClient):
        resp = await test_client.get("/api/agent-messages")
        assert resp.status_code == 200

    async def test_messages_empty_initially(self, test_client: AsyncClient):
        resp = await test_client.get("/api/agent-messages")
        assert resp.json() == []

    async def test_messages_populated_after_scenario(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/routine-restock")
        resp = await test_client.get("/api/agent-messages")
        messages = resp.json()
        assert len(messages) >= 1
        assert "agent_name" in messages[0]
        assert "intent_tag" in messages[0]


# ===================================================================
# POST /api/scenario/seed
# ===================================================================

class TestScenarioSeedEndpoint:

    async def test_seed_returns_200(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/seed")
        assert resp.status_code == 200

    async def test_seed_returns_counts(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/seed")
        data = resp.json()
        assert data["status"] == "seeded"
        assert data["closets"] == 5
        assert data["items"] == 10

    async def test_seed_is_idempotent(self, test_client: AsyncClient):
        resp1 = await test_client.post("/api/scenario/seed")
        resp2 = await test_client.post("/api/scenario/seed")
        assert resp1.json()["closets"] == resp2.json()["closets"]

    async def test_seed_clears_events(self, test_client: AsyncClient):
        # Run scenario to create events, then seed should clear them
        await test_client.post("/api/scenario/routine-restock")
        resp = await test_client.get("/api/events")
        assert len(resp.json()) > 0
        await test_client.post("/api/scenario/seed")
        resp = await test_client.get("/api/events")
        assert resp.json() == []


# ===================================================================
# POST /api/scenario/routine-restock
# ===================================================================

class TestRoutineRestockEndpoint:

    async def test_routine_restock_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/routine-restock")
        assert resp.status_code == 202

    async def test_routine_restock_returns_closet_id(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/routine-restock")
        data = resp.json()
        assert data["status"] == "started"
        assert data["scenario"] == "routine-restock"
        assert data["closet_id"] == "CLO-ICU-01"

    async def test_routine_restock_seeds_closets(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/routine-restock")
        state_resp = await test_client.get("/api/state")
        assert len(state_resp.json()["closets"]) == 5

    async def test_routine_restock_emits_event(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/routine-restock")
        events_resp = await test_client.get("/api/events")
        events = events_resp.json()
        types = [e["event_type"] for e in events]
        assert "ClosetScanInitiated" in types


# ===================================================================
# POST /api/scenario/critical-shortage
# ===================================================================

class TestCriticalShortageEndpoint:

    async def test_critical_shortage_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/critical-shortage")
        assert resp.status_code == 202

    async def test_critical_shortage_returns_closet_id(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/critical-shortage")
        data = resp.json()
        assert data["status"] == "started"
        assert data["scenario"] == "critical-shortage"
        assert data["closet_id"] == "CLO-SURG-01"

    async def test_critical_shortage_emits_event(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/critical-shortage")
        events_resp = await test_client.get("/api/events")
        events = events_resp.json()
        types = [e["event_type"] for e in events]
        assert "ClosetScanInitiated" in types
