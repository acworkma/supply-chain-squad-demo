"""
E2E scenario tests — verify full orchestration flows through the API.

Tests the complete ER admission and disruption-replan scenarios end-to-end,
plus edge cases (no beds, mutex, reset). Uses httpx AsyncClient with
ASGITransport (same pattern as test_endpoints.py). Background tasks
complete synchronously within the ASGI transport lifecycle.
"""

import pytest
from httpx import AsyncClient

from app.agents.orchestrator import run_scenario
from app.events.event_store import EventStore
from app.messages.message_store import MessageStore
from app.models.entities import Patient
from app.models.enums import BedState, PatientState
from app.state.store import StateStore


@pytest.fixture(autouse=True)
def fast_scenarios(monkeypatch):
    """Remove artificial delay from simulated orchestration steps."""
    monkeypatch.setattr("app.agents.orchestrator.STEP_DELAY", 0)


# ===================================================================
# ER Admission — End-to-End
# ===================================================================

class TestERAdmissionE2E:
    """Full ER admission scenario: seed → orchestrate → verify final state."""

    async def test_returns_202_with_patient_id(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/er-admission")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "started"
        assert data["scenario"] == "er-admission"
        assert "patient_id" in data

    async def test_patient_ends_arrived(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/er-admission")
        patient_id = resp.json()["patient_id"]

        state = (await test_client.get("/api/state")).json()
        assert state["patients"][patient_id]["state"] == "ARRIVED"

    async def test_assigned_bed_ends_occupied(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/er-admission")
        patient_id = resp.json()["patient_id"]

        state = (await test_client.get("/api/state")).json()
        patient = state["patients"][patient_id]
        bed_id = patient["assigned_bed_id"]
        assert bed_id is not None
        assert state["beds"][bed_id]["state"] == "OCCUPIED"

    async def test_correct_agents_participate(self, test_client: AsyncClient):
        """All five specialist agents should produce messages."""
        await test_client.post("/api/scenario/er-admission")

        messages = (await test_client.get("/api/agent-messages")).json()
        agent_names = {m["agent_name"] for m in messages}
        expected = {
            "bed-coordinator",
            "predictive-capacity",
            "policy-safety",
            "bed-allocation",
            "transport-ops",
        }
        assert expected.issubset(agent_names), (
            f"Missing agents: {expected - agent_names}"
        )

    async def test_intent_tags_propose_validate_execute(self, test_client: AsyncClient):
        """ER Admission uses PROPOSE, VALIDATE, and EXECUTE intent tags."""
        await test_client.post("/api/scenario/er-admission")

        messages = (await test_client.get("/api/agent-messages")).json()
        tags = {m["intent_tag"] for m in messages}
        assert "PROPOSE" in tags
        assert "VALIDATE" in tags
        assert "EXECUTE" in tags

    async def test_placement_complete_event_emitted(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/er-admission")

        events = (await test_client.get("/api/events")).json()
        placement = [e for e in events if e["event_type"] == "PlacementComplete"]
        assert len(placement) >= 1
        assert placement[-1]["payload"]["scenario"] == "er-admission"

    async def test_message_count_at_least_10(self, test_client: AsyncClient):
        """ER Admission should produce ≥10 agent messages (expects ~13)."""
        await test_client.post("/api/scenario/er-admission")

        messages = (await test_client.get("/api/agent-messages")).json()
        assert len(messages) >= 10

    async def test_events_include_bed_reserved(self, test_client: AsyncClient):
        """A BedReserved event should be emitted during placement."""
        await test_client.post("/api/scenario/er-admission")

        events = (await test_client.get("/api/events")).json()
        reserved = [e for e in events if e["event_type"] == "BedReserved"]
        assert len(reserved) >= 1

    async def test_transport_scheduled_event(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/er-admission")

        events = (await test_client.get("/api/events")).json()
        transport = [e for e in events if e["event_type"] == "TransportScheduled"]
        assert len(transport) >= 1


# ===================================================================
# Disruption + Replan — End-to-End
# ===================================================================

class TestDisruptionReplanE2E:
    """Full disruption scenario: seed → block bed → orchestrate → replan → verify."""

    async def test_returns_202_with_blocked_bed(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/disruption-replan")
        assert resp.status_code == 202
        data = resp.json()
        assert data["scenario"] == "disruption-replan"
        assert data.get("blocked_bed") is not None

    async def test_patient_ends_arrived(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/disruption-replan")
        patient_id = resp.json()["patient_id"]

        state = (await test_client.get("/api/state")).json()
        assert state["patients"][patient_id]["state"] == "ARRIVED"

    async def test_fallback_bed_differs_from_original(self, test_client: AsyncClient):
        """Disruption forces a different bed than the original assignment."""
        await test_client.post("/api/scenario/disruption-replan")

        events = (await test_client.get("/api/events")).json()
        placement = [e for e in events if e["event_type"] == "PlacementComplete"]
        assert len(placement) >= 1
        p = placement[-1]["payload"]
        assert p["bed_id"] != p["original_bed_id"]

    async def test_original_bed_ends_blocked(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/disruption-replan")

        events = (await test_client.get("/api/events")).json()
        placement = [e for e in events if e["event_type"] == "PlacementComplete"]
        original_bed_id = placement[-1]["payload"]["original_bed_id"]

        state = (await test_client.get("/api/state")).json()
        assert state["beds"][original_bed_id]["state"] == "BLOCKED"

    async def test_fallback_bed_ends_occupied(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/disruption-replan")

        events = (await test_client.get("/api/events")).json()
        placement = [e for e in events if e["event_type"] == "PlacementComplete"]
        fallback_bed_id = placement[-1]["payload"]["bed_id"]

        state = (await test_client.get("/api/state")).json()
        assert state["beds"][fallback_bed_id]["state"] == "OCCUPIED"

    async def test_escalate_intent_appears(self, test_client: AsyncClient):
        """Disruption scenario must produce at least one ESCALATE message."""
        await test_client.post("/api/scenario/disruption-replan")

        messages = (await test_client.get("/api/agent-messages")).json()
        escalate = [m for m in messages if m["intent_tag"] == "ESCALATE"]
        assert len(escalate) >= 1

    async def test_message_count_at_least_15(self, test_client: AsyncClient):
        """Disruption + replan should produce ≥15 messages (expects ~22)."""
        await test_client.post("/api/scenario/disruption-replan")

        messages = (await test_client.get("/api/agent-messages")).json()
        assert len(messages) >= 15

    async def test_placement_complete_event_is_disruption(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/disruption-replan")

        events = (await test_client.get("/api/events")).json()
        placement = [e for e in events if e["event_type"] == "PlacementComplete"]
        assert len(placement) >= 1
        p = placement[-1]["payload"]
        assert p["scenario"] == "disruption-replan"
        assert p["disruption"] == "bed_blocked"

    async def test_sla_risk_event_emitted(self, test_client: AsyncClient):
        """Disruption triggers an SLA risk escalation event."""
        await test_client.post("/api/scenario/disruption-replan")

        events = (await test_client.get("/api/events")).json()
        sla = [e for e in events if e["event_type"] == "SlaRiskDetected"]
        assert len(sla) >= 1


# ===================================================================
# EVS-Gated — End-to-End
# ===================================================================

class TestEvsGatedE2E:
    """EVS-gated scenario: dirty bed must be cleaned before assignment."""

    async def test_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/evs-gated")
        assert resp.status_code == 202
        data = resp.json()
        assert data["scenario"] == "evs-gated"
        assert "patient_id" in data

    async def test_patient_ends_arrived(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/evs-gated")
        patient_id = resp.json()["patient_id"]
        state = (await test_client.get("/api/state")).json()
        assert state["patients"][patient_id]["state"] == "ARRIVED"

    async def test_evs_task_created_event(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/evs-gated")
        events = (await test_client.get("/api/events")).json()
        evs = [e for e in events if e["event_type"] == "EVSTaskCreated"]
        assert len(evs) >= 1


# ===================================================================
# OR Admission — End-to-End
# ===================================================================

class TestOrAdmissionE2E:
    """OR admission scenario: post-surgical patient from OR."""

    async def test_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/or-admission")
        assert resp.status_code == 202
        data = resp.json()
        assert data["scenario"] == "or-admission"
        assert "patient_id" in data

    async def test_patient_ends_arrived(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/or-admission")
        patient_id = resp.json()["patient_id"]
        state = (await test_client.get("/api/state")).json()
        assert state["patients"][patient_id]["state"] == "ARRIVED"


# ===================================================================
# Unit Transfer — End-to-End
# ===================================================================

class TestUnitTransferE2E:
    """Unit transfer scenario: patient transfers between units."""

    async def test_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/unit-transfer")
        assert resp.status_code == 202
        data = resp.json()
        assert data["scenario"] == "unit-transfer"
        assert "patient_id" in data

    async def test_patient_ends_arrived(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/unit-transfer")
        patient_id = resp.json()["patient_id"]
        state = (await test_client.get("/api/state")).json()
        assert state["patients"][patient_id]["state"] == "ARRIVED"


# ===================================================================
# Edge Cases
# ===================================================================

class TestScenarioEdgeCases:

    async def test_no_ready_beds_returns_error(self, monkeypatch):
        """Orchestrator returns error when no READY beds exist."""
        monkeypatch.setattr("app.agents.orchestrator.STEP_DELAY", 0)
        ss = StateStore()
        es = EventStore()
        ms = MessageStore()

        ss.seed_initial_state()
        for bed in ss.beds.values():
            if bed.state == BedState.READY:
                bed.state = BedState.BLOCKED

        ss.patients["P-TEST"] = Patient(
            id="P-TEST",
            name="Test Patient",
            mrn="MRN-TEST",
            state=PatientState.AWAITING_BED,
            current_location="ED Bay 1",
            acuity_level=3,
        )

        result = await run_scenario("er-admission", ss, es, ms)
        assert not result["ok"]
        assert "No READY beds" in result.get("error", "")

    async def test_no_patient_awaiting_bed_returns_error(self, monkeypatch):
        """Orchestrator returns error when no patient is AWAITING_BED."""
        monkeypatch.setattr("app.agents.orchestrator.STEP_DELAY", 0)
        ss = StateStore()
        es = EventStore()
        ms = MessageStore()

        ss.seed_initial_state()
        ss.patients.clear()

        result = await run_scenario("er-admission", ss, es, ms)
        assert not result["ok"]
        assert "No patient awaiting bed" in result.get("error", "")

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
            resp = await test_client.post("/api/scenario/er-admission")
            assert resp.status_code == 409
            assert "already running" in resp.json()["error"]
        finally:
            _scenario_lock.release()

    async def test_concurrent_disruption_returns_409(self, test_client: AsyncClient):
        """Disruption endpoint also respects the mutex."""
        from app.routers.scenarios import _scenario_lock

        await _scenario_lock.acquire()
        try:
            resp = await test_client.post("/api/scenario/disruption-replan")
            assert resp.status_code == 409
            assert "already running" in resp.json()["error"]
        finally:
            _scenario_lock.release()

    async def test_seed_clears_events_and_messages(self, test_client: AsyncClient):
        """Seeding after a scenario clears all events and messages."""
        await test_client.post("/api/scenario/er-admission")

        assert len((await test_client.get("/api/events")).json()) > 0
        assert len((await test_client.get("/api/agent-messages")).json()) > 0

        await test_client.post("/api/scenario/seed")

        assert (await test_client.get("/api/events")).json() == []
        assert (await test_client.get("/api/agent-messages")).json() == []

    async def test_seed_restores_fresh_state(self, test_client: AsyncClient):
        """After scenario completion, seed restores the standard 12 beds / 4 patients."""
        await test_client.post("/api/scenario/er-admission")
        await test_client.post("/api/scenario/seed")

        state = (await test_client.get("/api/state")).json()
        assert len(state["beds"]) == 16
        assert len(state["patients"]) == 5

    async def test_disruption_no_fallback_beds(self, monkeypatch):
        """Disruption returns error when all beds are blocked (no fallback)."""
        monkeypatch.setattr("app.agents.orchestrator.STEP_DELAY", 0)
        ss = StateStore()
        es = EventStore()
        ms = MessageStore()

        ss.seed_initial_state()

        # Leave only one READY bed so the orchestrator can reserve it,
        # but no fallback exists after the disruption blocks it.
        ready_beds = [b for b in ss.beds.values() if b.state == BedState.READY]
        for bed in ready_beds[1:]:
            bed.state = BedState.BLOCKED

        ss.patients["P-TEST"] = Patient(
            id="P-TEST",
            name="Test Patient",
            mrn="MRN-TEST",
            state=PatientState.AWAITING_BED,
            current_location="ED Bay 1",
            acuity_level=4,
        )

        result = await run_scenario("disruption-replan", ss, es, ms)
        assert not result["ok"]
        assert "fallback" in result.get("error", "").lower() or "No READY" in result.get("error", "")
