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
        for key in ("beds", "patients", "tasks", "transports", "reservations"):
            assert key in data, f"Missing key: {key}"

    async def test_state_beds_are_dict(self, test_client: AsyncClient):
        resp = await test_client.get("/api/state")
        assert isinstance(resp.json()["beds"], dict)

    async def test_state_after_seed(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/seed")
        resp = await test_client.get("/api/state")
        data = resp.json()
        assert len(data["beds"]) == 16
        assert len(data["patients"]) == 5


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
        await test_client.post("/api/scenario/er-admission")
        resp = await test_client.get("/api/events")
        events = resp.json()
        assert len(events) >= 1

    async def test_events_since_filter(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/er-admission")
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
        await test_client.post("/api/scenario/er-admission")
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
        assert data["beds"] == 16
        assert data["patients"] == 5

    async def test_seed_is_idempotent(self, test_client: AsyncClient):
        resp1 = await test_client.post("/api/scenario/seed")
        resp2 = await test_client.post("/api/scenario/seed")
        assert resp1.json()["beds"] == resp2.json()["beds"]

    async def test_seed_clears_events(self, test_client: AsyncClient):
        # Run scenario to create events, then seed should clear them
        await test_client.post("/api/scenario/er-admission")
        resp = await test_client.get("/api/events")
        assert len(resp.json()) > 0
        await test_client.post("/api/scenario/seed")
        resp = await test_client.get("/api/events")
        assert resp.json() == []


# ===================================================================
# POST /api/scenario/er-admission
# ===================================================================

class TestErAdmissionEndpoint:

    async def test_er_admission_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/er-admission")
        assert resp.status_code == 202

    async def test_er_admission_returns_patient_id(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/er-admission")
        data = resp.json()
        assert data["status"] == "started"
        assert data["scenario"] == "er-admission"
        assert "patient_id" in data
        assert data["patient_id"].startswith("P-")

    async def test_er_admission_creates_patient(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/er-admission")
        patient_id = resp.json()["patient_id"]
        state_resp = await test_client.get("/api/state")
        patients = state_resp.json()["patients"]
        assert patient_id in patients
        assert patients[patient_id]["name"] == "Sarah Johnson"

    async def test_er_admission_seeds_16_beds(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/er-admission")
        state_resp = await test_client.get("/api/state")
        assert len(state_resp.json()["beds"]) == 16

    async def test_er_admission_emits_event(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/er-admission")
        events_resp = await test_client.get("/api/events")
        events = events_resp.json()
        types = [e["event_type"] for e in events]
        assert "PatientBedRequestCreated" in types


# ===================================================================
# POST /api/scenario/disruption-replan
# ===================================================================

class TestDisruptionReplanEndpoint:

    async def test_disruption_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/disruption-replan")
        assert resp.status_code == 202

    async def test_disruption_returns_patient_and_blocked_bed(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/disruption-replan")
        data = resp.json()
        assert data["status"] == "started"
        assert data["scenario"] == "disruption-replan"
        assert "patient_id" in data
        assert "blocked_bed" in data

    async def test_disruption_creates_patient(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/disruption-replan")
        patient_id = resp.json()["patient_id"]
        state_resp = await test_client.get("/api/state")
        patients = state_resp.json()["patients"]
        assert patient_id in patients
        assert patients[patient_id]["name"] == "David Park"

    async def test_disruption_blocks_a_bed(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/disruption-replan")
        blocked_bed_id = resp.json()["blocked_bed"]
        if blocked_bed_id:
            state_resp = await test_client.get("/api/state")
            bed = state_resp.json()["beds"][blocked_bed_id]
            assert bed["state"] == "BLOCKED"

    async def test_disruption_emits_event(self, test_client: AsyncClient):
        await test_client.post("/api/scenario/disruption-replan")
        events_resp = await test_client.get("/api/events")
        events = events_resp.json()
        types = [e["event_type"] for e in events]
        assert "PatientBedRequestCreated" in types


# ===================================================================
# POST /api/scenario/evs-gated
# ===================================================================

class TestEvsGatedEndpoint:

    async def test_evs_gated_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/evs-gated")
        assert resp.status_code == 202

    async def test_evs_gated_returns_patient_id(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/evs-gated")
        data = resp.json()
        assert data["scenario"] == "evs-gated"
        assert data["patient_id"].startswith("P-")


# ===================================================================
# POST /api/scenario/or-admission
# ===================================================================

class TestOrAdmissionEndpoint:

    async def test_or_admission_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/or-admission")
        assert resp.status_code == 202

    async def test_or_admission_returns_patient_id(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/or-admission")
        data = resp.json()
        assert data["scenario"] == "or-admission"
        assert data["patient_id"].startswith("P-")


# ===================================================================
# POST /api/scenario/unit-transfer
# ===================================================================

class TestUnitTransferEndpoint:

    async def test_unit_transfer_returns_202(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/unit-transfer")
        assert resp.status_code == 202

    async def test_unit_transfer_returns_patient_id(self, test_client: AsyncClient):
        resp = await test_client.post("/api/scenario/unit-transfer")
        data = resp.json()
        assert data["scenario"] == "unit-transfer"
        assert data["patient_id"].startswith("P-")
