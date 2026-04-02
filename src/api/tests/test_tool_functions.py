"""
Tool function tests — every agent-callable tool (ADR-003/003a).

Each tool receives state_store, event_store, message_store as kwargs.
We verify state mutations, event emissions, message publishing, and error paths.
"""

import pytest

from app.events.event_store import EventStore
from app.messages.message_store import MessageStore
from app.models.entities import Bed, Patient
from app.models.enums import (
    BedState,
    IntentTag,
    PatientState,
    TaskState,
    TaskType,
    TransportPriority,
)
from app.models.events import (
    BED_RESERVED,
    EVS_TASK_CREATED,
    EVS_TASK_STATUS_CHANGED,
    RESERVATION_RELEASED,
    SLA_RISK_DETECTED,
    TRANSPORT_SCHEDULED,
)
from app.models.transitions import InvalidTransitionError
from app.state.store import StateStore
from app.tools.tool_functions import (
    create_task,
    escalate,
    get_beds,
    get_patient,
    get_tasks,
    publish_event,
    release_bed_reservation,
    reserve_bed,
    schedule_transport,
    update_task,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _seed_bed(store: StateStore, bed_id: str = "BED-101A", state: BedState = BedState.READY, unit: str = "4-North") -> Bed:
    bed = Bed(id=bed_id, unit=unit, room_number="101", bed_letter="A", state=state)
    store.beds[bed_id] = bed
    return bed


def _seed_patient(store: StateStore, patient_id: str = "P-001", state: PatientState = PatientState.AWAITING_BED) -> Patient:
    patient = Patient(id=patient_id, name="Test Patient", mrn="MRN-001", current_location="ED Bay 1", state=state)
    store.patients[patient_id] = patient
    return patient


# ===================================================================
# get_patient
# ===================================================================

class TestGetPatient:

    async def test_returns_patient_data(self, state_store: StateStore):
        _seed_patient(state_store, "P-001")
        result = await get_patient("P-001", state_store=state_store)
        assert result["ok"] is True
        assert result["patient"]["id"] == "P-001"
        assert result["patient"]["name"] == "Test Patient"

    async def test_not_found(self, state_store: StateStore):
        result = await get_patient("P-MISSING", state_store=state_store)
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_returns_all_patient_fields(self, state_store: StateStore):
        _seed_patient(state_store, "P-002")
        result = await get_patient("P-002", state_store=state_store)
        patient = result["patient"]
        assert "id" in patient
        assert "name" in patient
        assert "mrn" in patient
        assert "state" in patient
        assert "current_location" in patient


# ===================================================================
# get_beds
# ===================================================================

class TestGetBeds:

    async def test_returns_all_beds(self, state_store: StateStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_bed(state_store, "BED-2", BedState.DIRTY)
        result = await get_beds(state_store=state_store)
        assert result["ok"] is True
        assert len(result["beds"]) == 2

    async def test_filter_by_unit(self, state_store: StateStore):
        _seed_bed(state_store, "BED-1", unit="4-North")
        _seed_bed(state_store, "BED-2", unit="5-South")
        result = await get_beds(state_store=state_store, unit="4-North")
        assert len(result["beds"]) == 1
        assert result["beds"][0]["unit"] == "4-North"

    async def test_filter_by_state(self, state_store: StateStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_bed(state_store, "BED-2", BedState.DIRTY)
        result = await get_beds(state_store=state_store, state="READY")
        assert len(result["beds"]) == 1
        assert result["beds"][0]["state"] == "READY"

    async def test_filter_by_unit_and_state(self, state_store: StateStore):
        _seed_bed(state_store, "BED-1", BedState.READY, unit="4-North")
        _seed_bed(state_store, "BED-2", BedState.DIRTY, unit="4-North")
        _seed_bed(state_store, "BED-3", BedState.READY, unit="5-South")
        result = await get_beds(state_store=state_store, unit="4-North", state="READY")
        assert len(result["beds"]) == 1
        assert result["beds"][0]["id"] == "BED-1"

    async def test_empty_store(self, state_store: StateStore):
        result = await get_beds(state_store=state_store)
        assert result["ok"] is True
        assert result["beds"] == []

    async def test_filter_by_diagnosis(self, state_store: StateStore):
        """Diagnosis filter narrows beds to clinically appropriate units."""
        _seed_bed(state_store, "BED-1", BedState.READY, unit="4-North")
        _seed_bed(state_store, "BED-2", BedState.READY, unit="5-South")
        result = await get_beds(state_store=state_store, diagnosis="chest pain")
        assert result["ok"] is True
        # chest pain → Cardiac/Telemetry → 5-South only
        assert len(result["beds"]) == 1
        assert result["beds"][0]["unit"] == "5-South"

    async def test_filter_by_diagnosis_medsurg(self, state_store: StateStore):
        """Pneumonia maps to Med/Surg units (4-North and 2-East)."""
        _seed_bed(state_store, "BED-1", BedState.READY, unit="4-North")
        _seed_bed(state_store, "BED-2", BedState.READY, unit="5-South")
        _seed_bed(state_store, "BED-3", BedState.READY, unit="2-East")
        result = await get_beds(state_store=state_store, diagnosis="pneumonia")
        assert result["ok"] is True
        units = {b["unit"] for b in result["beds"]}
        assert "4-North" in units
        assert "2-East" in units
        assert "5-South" not in units

# ===================================================================
# get_tasks
# ===================================================================

class TestGetTasks:

    async def test_returns_all_tasks(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        await create_task("TRANSPORT", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        result = await get_tasks(state_store=state_store)
        assert result["ok"] is True
        assert len(result["tasks"]) == 2

    async def test_filter_by_state(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        r = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        result = await get_tasks(state_store=state_store, task_state="CREATED")
        assert len(result["tasks"]) == 1

    async def test_filter_by_type(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        await create_task("TRANSPORT", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        result = await get_tasks(state_store=state_store, task_type="TRANSPORT")
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["type"] == "TRANSPORT"

    async def test_empty_store(self, state_store: StateStore):
        result = await get_tasks(state_store=state_store)
        assert result["ok"] is True
        assert result["tasks"] == []


# ===================================================================
# reserve_bed
# ===================================================================

class TestReserveBed:

    async def test_reserves_ready_bed(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        result = await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["bed_id"] == "BED-1"
        assert result["patient_id"] == "P-1"
        assert "reservation_id" in result
        assert "hold_until" in result

    async def test_bed_transitions_to_reserved(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert state_store.get_bed("BED-1").state == BedState.RESERVED

    async def test_creates_reservation_entity(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        result = await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        reservations = state_store.get_active_reservations()
        assert len(reservations) == 1
        assert reservations[0].bed_id == "BED-1"
        assert reservations[0].patient_id == "P-1"
        assert reservations[0].is_active is True

    async def test_emits_bed_reserved_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        events = event_store.get_events()
        assert len(events) == 1
        assert events[0].event_type == BED_RESERVED
        assert events[0].entity_id == "BED-1"
        assert events[0].state_diff.from_state == "READY"
        assert events[0].state_diff.to_state == "RESERVED"

    async def test_publishes_message(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        messages = message_store.get_messages()
        assert len(messages) == 1
        assert messages[0].intent_tag == IntentTag.EXECUTE
        assert "BED-1" in messages[0].content

    async def test_bed_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_patient(state_store, "P-1")
        result = await reserve_bed("BED-FAKE", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_patient_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        result = await reserve_bed("BED-1", "P-FAKE", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_invalid_transition_returns_error(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.OCCUPIED)
        _seed_patient(state_store, "P-1")
        result = await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False

    async def test_custom_hold_minutes(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        result = await reserve_bed("BED-1", "P-1", hold_minutes=60, state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        events = event_store.get_events()
        assert events[0].payload["hold_minutes"] == 60


# ===================================================================
# release_bed_reservation
# ===================================================================

class TestReleaseBedReservation:

    async def test_releases_reservation(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)

        result = await release_bed_reservation("BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["bed_id"] == "BED-1"

    async def test_bed_transitions_back_to_ready(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        await release_bed_reservation("BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert state_store.get_bed("BED-1").state == BedState.READY

    async def test_deactivates_reservation(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        await release_bed_reservation("BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        active = state_store.get_active_reservations()
        assert len(active) == 0

    async def test_emits_reservation_released_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_bed(state_store, "BED-1", BedState.READY)
        _seed_patient(state_store, "P-1")
        await reserve_bed("BED-1", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        event_store.clear()  # clear the reserve event to isolate release
        await release_bed_reservation("BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        events = event_store.get_events()
        assert any(e.event_type == RESERVATION_RELEASED for e in events)

    async def test_bed_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await release_bed_reservation("BED-FAKE", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False


# ===================================================================
# create_task
# ===================================================================

class TestCreateTask:

    async def test_creates_evs_task(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["type"] == "EVS_CLEANING"
        assert result["subject_id"] == "BED-1"
        assert "task_id" in result

    async def test_task_stored_in_state(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        task = state_store.get_task(result["task_id"])
        assert task is not None
        assert task.type == TaskType.EVS_CLEANING
        assert task.state == TaskState.CREATED
        assert task.subject_id == "BED-1"

    async def test_emits_evs_task_created_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        events = event_store.get_events()
        assert len(events) == 1
        assert events[0].event_type == EVS_TASK_CREATED

    async def test_publishes_message(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        messages = message_store.get_messages()
        assert len(messages) == 1
        assert messages[0].intent_tag == IntentTag.EXECUTE

    async def test_priority_defaults_to_routine(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        task = state_store.get_task(result["task_id"])
        assert task.priority == TransportPriority.ROUTINE

    async def test_explicit_priority(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await create_task("EVS_CLEANING", "BED-1", priority="STAT", state_store=state_store, event_store=event_store, message_store=message_store)
        task = state_store.get_task(result["task_id"])
        assert task.priority == TransportPriority.STAT

    async def test_transport_task_type(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await create_task("TRANSPORT", "P-1", state_store=state_store, event_store=event_store, message_store=message_store)
        task = state_store.get_task(result["task_id"])
        assert task.type == TaskType.TRANSPORT


# ===================================================================
# update_task
# ===================================================================

class TestUpdateTask:

    async def test_transitions_task_state(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        cr = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        result = await update_task(cr["task_id"], "ACCEPTED", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["old_state"] == "CREATED"
        assert result["new_state"] == "ACCEPTED"

    async def test_task_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await update_task("TASK-FAKE", "ACCEPTED", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_invalid_transition_returns_error(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        cr = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        result = await update_task(cr["task_id"], "COMPLETED", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False

    async def test_emits_status_changed_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        cr = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        event_store.clear()
        await update_task(cr["task_id"], "ACCEPTED", state_store=state_store, event_store=event_store, message_store=message_store)
        events = event_store.get_events()
        assert any(e.event_type == EVS_TASK_STATUS_CHANGED for e in events)
        evt = [e for e in events if e.event_type == EVS_TASK_STATUS_CHANGED][0]
        assert evt.state_diff.from_state == "CREATED"
        assert evt.state_diff.to_state == "ACCEPTED"

    async def test_eta_minutes_updated(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        cr = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        await update_task(cr["task_id"], "ACCEPTED", eta_minutes=15, state_store=state_store, event_store=event_store, message_store=message_store)
        task = state_store.get_task(cr["task_id"])
        assert task.eta_minutes == 15

    async def test_accepted_sets_accepted_at(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        cr = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        await update_task(cr["task_id"], "ACCEPTED", state_store=state_store, event_store=event_store, message_store=message_store)
        task = state_store.get_task(cr["task_id"])
        assert task.accepted_at is not None

    async def test_completed_sets_completed_at(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        cr = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        await update_task(cr["task_id"], "ACCEPTED", state_store=state_store, event_store=event_store, message_store=message_store)
        await update_task(cr["task_id"], "IN_PROGRESS", state_store=state_store, event_store=event_store, message_store=message_store)
        await update_task(cr["task_id"], "COMPLETED", state_store=state_store, event_store=event_store, message_store=message_store)
        task = state_store.get_task(cr["task_id"])
        assert task.completed_at is not None

    async def test_full_lifecycle(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        cr = await create_task("EVS_CLEANING", "BED-1", state_store=state_store, event_store=event_store, message_store=message_store)
        tid = cr["task_id"]
        for status in ["ACCEPTED", "IN_PROGRESS", "COMPLETED"]:
            result = await update_task(tid, status, state_store=state_store, event_store=event_store, message_store=message_store)
            assert result["ok"] is True
        assert state_store.get_task(tid).state == TaskState.COMPLETED


# ===================================================================
# schedule_transport
# ===================================================================

class TestScheduleTransport:

    async def test_creates_transport(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_patient(state_store, "P-1")
        result = await schedule_transport(
            "P-1", "ED Bay 1", "4-North 401A",
            state_store=state_store, event_store=event_store, message_store=message_store,
        )
        assert result["ok"] is True
        assert result["patient_id"] == "P-1"
        assert "transport_id" in result

    async def test_transport_stored_in_state(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_patient(state_store, "P-1")
        result = await schedule_transport(
            "P-1", "ED Bay 1", "4-North 401A",
            state_store=state_store, event_store=event_store, message_store=message_store,
        )
        transport = state_store.get_transport(result["transport_id"])
        assert transport is not None
        assert transport.patient_id == "P-1"
        assert transport.from_location == "ED Bay 1"
        assert transport.to_location == "4-North 401A"
        assert transport.state == TaskState.CREATED

    async def test_emits_transport_scheduled_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_patient(state_store, "P-1")
        await schedule_transport(
            "P-1", "ED Bay 1", "4-North 401A",
            state_store=state_store, event_store=event_store, message_store=message_store,
        )
        events = event_store.get_events()
        assert len(events) == 1
        assert events[0].event_type == TRANSPORT_SCHEDULED

    async def test_publishes_message(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_patient(state_store, "P-1")
        await schedule_transport(
            "P-1", "ED Bay 1", "4-North 401A",
            state_store=state_store, event_store=event_store, message_store=message_store,
        )
        messages = message_store.get_messages()
        assert len(messages) == 1
        assert messages[0].agent_name == "transport-ops"
        assert messages[0].intent_tag == IntentTag.EXECUTE

    async def test_patient_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await schedule_transport(
            "P-FAKE", "ED", "Room",
            state_store=state_store, event_store=event_store, message_store=message_store,
        )
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_custom_priority(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_patient(state_store, "P-1")
        result = await schedule_transport(
            "P-1", "ED", "Room", priority="STAT",
            state_store=state_store, event_store=event_store, message_store=message_store,
        )
        transport = state_store.get_transport(result["transport_id"])
        assert transport.priority == TransportPriority.STAT


# ===================================================================
# publish_event
# ===================================================================

class TestPublishEvent:

    async def test_emits_generic_event(self, event_store: EventStore):
        result = await publish_event(
            "CustomEvent", "entity-1", {"key": "value"},
            event_store=event_store,
        )
        assert result["ok"] is True
        assert "event_id" in result
        assert result["sequence"] >= 1

    async def test_event_stored(self, event_store: EventStore):
        await publish_event("CustomEvent", "entity-1", event_store=event_store)
        events = event_store.get_events()
        assert len(events) == 1
        assert events[0].event_type == "CustomEvent"
        assert events[0].entity_id == "entity-1"

    async def test_empty_payload_defaults(self, event_store: EventStore):
        await publish_event("Test", "e-1", event_store=event_store)
        events = event_store.get_events()
        assert events[0].payload == {}


# ===================================================================
# escalate
# ===================================================================

class TestEscalate:

    async def test_emits_sla_risk_event(self, event_store: EventStore, message_store: MessageStore):
        result = await escalate(
            "SLA_BREACH", "BED-1", "HIGH", "Cleaning overdue",
            event_store=event_store, message_store=message_store,
        )
        assert result["ok"] is True
        assert result["issue_type"] == "SLA_BREACH"
        assert result["severity"] == "HIGH"

    async def test_event_type_is_sla_risk(self, event_store: EventStore, message_store: MessageStore):
        await escalate(
            "SLA_BREACH", "BED-1", "HIGH", "Cleaning overdue",
            event_store=event_store, message_store=message_store,
        )
        events = event_store.get_events()
        assert events[0].event_type == SLA_RISK_DETECTED
        assert events[0].payload["severity"] == "HIGH"

    async def test_publishes_escalation_message(self, event_store: EventStore, message_store: MessageStore):
        await escalate(
            "SLA_BREACH", "BED-1", "HIGH", "Cleaning overdue",
            event_store=event_store, message_store=message_store,
        )
        messages = message_store.get_messages()
        assert len(messages) == 1
        assert messages[0].intent_tag == IntentTag.ESCALATE
        assert messages[0].agent_name == "policy-safety"
        assert "ESCALATION" in messages[0].content
