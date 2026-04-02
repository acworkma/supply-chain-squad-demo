"""
E2E scenario tests — verify full orchestration flows through the API.

Tests the complete routine-restock and critical-shortage scenarios end-to-end,
plus edge cases (unknown scenario, mutex, reset). Uses httpx AsyncClient with
ASGITransport (same pattern as test_endpoints.py). Background tasks
complete synchronously within the ASGI transport lifecycle.
"""

import pytest
from httpx import AsyncClient

from app.agents.orchestrator import run_scenario
from app.events.event_store import EventStore
from app.messages.message_store import MessageStore
from app.state.store import StateStore


@pytest.fixture(autouse=True)
def fast_scenarios(monkeypatch):
    """Remove artificial delay from simulated orchestration steps."""
    monkeypatch.setattr("app.agents.orchestrator.STEP_DELAY", 0)


# ===================================================================
# Routine Restock — End-to-End
# ===================================================================

class TestRoutineRestockE2E:
    """Full routine restock scenario: seed → scan → order → ship → restock."""

    async def test_returns_202_with_closet_id(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/routine-restock")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "started"
        assert data["scenario"] == "routine-restock"
        assert data["closet_id"] == "CLO-ICU-01"

    async def test_scan_created_in_state(self, test_client: AsyncClient):
        """After orchestration, at least one scan should exist in state."""
        await test_client.post("/api/scenario/routine-restock")
        state = (await test_client.get("/api/state")).json()
        assert len(state["scans"]) >= 1

    async def test_purchase_order_created(self, test_client: AsyncClient):
        """A PO should be created during routine restock."""
        await test_client.post("/api/scenario/routine-restock")
        state = (await test_client.get("/api/state")).json()
        assert len(state["purchase_orders"]) >= 1

    async def test_shipment_created(self, test_client: AsyncClient):
        """A shipment should be created for the PO."""
        await test_client.post("/api/scenario/routine-restock")
        state = (await test_client.get("/api/state")).json()
        assert len(state["shipments"]) >= 1

    async def test_correct_agents_participate(self, test_client: AsyncClient):
        """All five specialist agents should produce messages."""
        await test_client.post("/api/scenario/routine-restock")

        messages = (await test_client.get("/api/agent-messages")).json()
        agent_names = {m["agent_name"] for m in messages}
        expected = {
            "supply-coordinator",
            "supply-scanner",
            "catalog-sourcer",
            "order-manager",
            "compliance-gate",
        }
        assert expected.issubset(agent_names), (
            f"Missing agents: {expected - agent_names}"
        )

    async def test_intent_tags_propose_validate_execute(self, test_client: AsyncClient):
        """Routine restock uses PROPOSE, VALIDATE, and EXECUTE intent tags."""
        await test_client.post("/api/scenario/routine-restock")

        messages = (await test_client.get("/api/agent-messages")).json()
        tags = {m["intent_tag"] for m in messages}
        assert "PROPOSE" in tags
        assert "VALIDATE" in tags
        assert "EXECUTE" in tags

    async def test_scan_initiated_event_emitted(self, test_client: AsyncClient):
        """A ClosetScanInitiated event should be emitted."""
        await test_client.post("/api/scenario/routine-restock")

        events = (await test_client.get("/api/events")).json()
        types = [e["event_type"] for e in events]
        assert "ClosetScanInitiated" in types

    async def test_po_created_event_emitted(self, test_client: AsyncClient):
        """A POCreated event should be emitted."""
        await test_client.post("/api/scenario/routine-restock")

        events = (await test_client.get("/api/events")).json()
        types = [e["event_type"] for e in events]
        assert "POCreated" in types

    async def test_shipment_delivered_event_emitted(self, test_client: AsyncClient):
        """A ShipmentDelivered event should be emitted."""
        await test_client.post("/api/scenario/routine-restock")

        events = (await test_client.get("/api/events")).json()
        types = [e["event_type"] for e in events]
        assert "ShipmentDelivered" in types

    async def test_closet_restocked_event_emitted(self, test_client: AsyncClient):
        """A ClosetRestocked event should be emitted."""
        await test_client.post("/api/scenario/routine-restock")

        events = (await test_client.get("/api/events")).json()
        types = [e["event_type"] for e in events]
        assert "ClosetRestocked" in types

    async def test_message_count_at_least_10(self, test_client: AsyncClient):
        """Routine restock should produce ≥10 agent messages."""
        await test_client.post("/api/scenario/routine-restock")

        messages = (await test_client.get("/api/agent-messages")).json()
        assert len(messages) >= 10


# ===================================================================
# Critical Shortage — End-to-End
# ===================================================================

class TestCriticalShortageE2E:
    """Full critical shortage scenario: scan → escalate → emergency PO → ship → restock."""

    async def test_returns_202_with_closet_id(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/critical-shortage")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "started"
        assert data["scenario"] == "critical-shortage"
        assert data["closet_id"] == "CLO-SURG-01"

    async def test_scan_created_in_state(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/critical-shortage")
        state = (await test_client.get("/api/state")).json()
        assert len(state["scans"]) >= 1

    async def test_purchase_order_created(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/critical-shortage")
        state = (await test_client.get("/api/state")).json()
        assert len(state["purchase_orders"]) >= 1

    async def test_shipment_created(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/critical-shortage")
        state = (await test_client.get("/api/state")).json()
        assert len(state["shipments"]) >= 1

    async def test_escalate_intent_appears(self, test_client: AsyncClient):
        """Critical shortage must produce at least one ESCALATE message."""
        await test_client.post("/api/scenario/critical-shortage")

        messages = (await test_client.get("/api/agent-messages")).json()
        escalate = [m for m in messages if m["intent_tag"] == "ESCALATE"]
        assert len(escalate) >= 1

    async def test_critical_shortage_event_emitted(self, test_client: AsyncClient):
        """A CriticalShortageDetected event should be emitted."""
        await test_client.post("/api/scenario/critical-shortage")

        events = (await test_client.get("/api/events")).json()
        types = [e["event_type"] for e in events]
        assert "CriticalShortageDetected" in types

    async def test_po_auto_or_human_approved(self, test_client: AsyncClient):
        """Critical PO should be either auto-approved or human-approved."""
        await test_client.post("/api/scenario/critical-shortage")

        events = (await test_client.get("/api/events")).json()
        types = [e["event_type"] for e in events]
        has_approval = "POAutoApproved" in types or "POHumanApproved" in types
        assert has_approval

    async def test_correct_agents_participate(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/critical-shortage")

        messages = (await test_client.get("/api/agent-messages")).json()
        agent_names = {m["agent_name"] for m in messages}
        expected = {
            "supply-coordinator",
            "supply-scanner",
            "compliance-gate",
        }
        assert expected.issubset(agent_names), (
            f"Missing agents: {expected - agent_names}"
        )

    async def test_message_count_at_least_10(self, test_client: AsyncClient):
        """Critical shortage should produce ≥10 agent messages."""
        await test_client.post("/api/scenario/critical-shortage")

        messages = (await test_client.get("/api/agent-messages")).json()
        assert len(messages) >= 10


# ===================================================================
# Edge Cases
# ===================================================================

class TestScenarioEdgeCases:

    async def test_unknown_scenario_returns_error(self, monkeypatch):
        """run_scenario rejects unknown scenario types."""
        monkeypatch.setattr("app.agents.orchestrator.STEP_DELAY", 0)
        ss = StateStore()
        es = EventStore()
        ms = MessageStore()

        result = await run_scenario("nonexistent", ss, es, ms)
        assert not result["ok"]
        assert "Unknown scenario" in result.get("error", "")

    async def test_concurrent_scenario_returns_409(self, test_client: AsyncClient):
        """A 409 is returned when a scenario is already running."""
        from app.routers.scenarios import _scenario_lock

        await _scenario_lock.acquire()
        try:
            resp = await test_client.post("/api/scenario/routine-restock")
            assert resp.status_code == 409
            assert "already running" in resp.json()["error"]
        finally:
            _scenario_lock.release()

    async def test_concurrent_critical_returns_409(self, test_client: AsyncClient):
        """Critical shortage endpoint also respects the mutex."""
        from app.routers.scenarios import _scenario_lock

        await _scenario_lock.acquire()
        try:
            resp = await test_client.post("/api/scenario/critical-shortage")
            assert resp.status_code == 409
            assert "already running" in resp.json()["error"]
        finally:
            _scenario_lock.release()

    async def test_seed_then_restock(self, test_client: AsyncClient):
        """Seed + restock should work sequentially."""
        await test_client.post("/api/scenario/seed")
        resp = await test_client.post("/api/scenario/routine-restock")
        assert resp.status_code == 202

    async def test_seed_clears_events(self, test_client: AsyncClient):
        """Seed endpoint clears events from prior runs."""
        await test_client.post("/api/scenario/routine-restock")
        resp = await test_client.get("/api/events")
        assert len(resp.json()) > 0
        await test_client.post("/api/scenario/seed")
        resp = await test_client.get("/api/events")
        assert resp.json() == []

    async def test_seed_clears_events_and_messages(self, test_client: AsyncClient):
        """Seeding after a scenario clears all events and messages."""
        await test_client.post("/api/scenario/routine-restock")

        assert len((await test_client.get("/api/events")).json()) > 0
        assert len((await test_client.get("/api/agent-messages")).json()) > 0

        await test_client.post("/api/scenario/seed")

        assert (await test_client.get("/api/events")).json() == []
        assert (await test_client.get("/api/agent-messages")).json() == []

    async def test_seed_restores_fresh_state(self, test_client: AsyncClient):
        """After scenario completion, seed restores 5 closets / 10 items."""
        await test_client.post("/api/scenario/routine-restock")
        await test_client.post("/api/scenario/seed")

        state = (await test_client.get("/api/state")).json()
        assert len(state["closets"]) == 5
        assert len(state["items"]) == 10
