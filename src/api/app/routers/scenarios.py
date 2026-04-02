"""Scenario trigger endpoints — start demo workflows."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from app.agents.orchestrator import run_scenario
from app.events import event_store
from app.messages import message_store
from app.metrics import metrics_store
from app.models.entities import Patient
from app.models.enums import AdmissionSource, BedState, IntentTag, PatientState
from app.models.events import PATIENT_BED_REQUEST_CREATED
from app.state import store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scenarios"])

# Mutex to prevent concurrent scenario runs (ADR-007)
_scenario_lock = asyncio.Lock()


def _reset_and_seed() -> None:
    """Clear all stores and re-seed the initial hospital state."""
    store.clear()
    store.seed_initial_state()
    event_store.clear()
    message_store.clear()


@router.post("/scenario/seed")
async def seed_state():
    """Reset state and seed beds/patients without starting orchestration."""
    _reset_and_seed()
    return {"status": "seeded", "beds": len(store.beds), "patients": len(store.patients)}


@router.post("/scenario/er-admission")
async def run_er_admission(background_tasks: BackgroundTasks):
    """Trigger the ER admission scenario (ADR-007).

    Clears state, seeds initial conditions, adds a new incoming patient,
    and emits the PatientBedRequestCreated event.
    Returns 202 immediately — orchestration runs as a background task.
    """
    if _scenario_lock.locked():
        return JSONResponse(status_code=409, content={"error": "A scenario is already running"})

    _reset_and_seed()

    # Add a new incoming patient needing a bed
    now = datetime.now(timezone.utc)
    patient = Patient(
        id=f"P-{uuid.uuid4().hex[:6].upper()}",
        name="Sarah Johnson",
        mrn="MRN-20001",
        state=PatientState.AWAITING_BED,
        current_location="ED Bay 3",
        diagnosis="Chest pain — rule out ACS",
        acuity_level=3,
        requested_at=now,
    )
    store.patients[patient.id] = patient

    await event_store.publish(
        event_type=PATIENT_BED_REQUEST_CREATED,
        entity_id=patient.id,
        payload={"patient_id": patient.id, "name": patient.name, "acuity": patient.acuity_level, "location": patient.current_location},
    )

    await message_store.publish(
        agent_name="bed-coordinator",
        agent_role="Bed Coordinator Assistant",
        content=f"New bed request received for patient {patient.name} ({patient.id}) from {patient.current_location}. Acuity: {patient.acuity_level}. Diagnosis: {patient.diagnosis}. Initiating placement workflow.",
        intent_tag=IntentTag.PROPOSE,
    )

    async def _run_orchestration():
        async with _scenario_lock:
            try:
                result = await run_scenario("er-admission", store, event_store, message_store)
                logger.info("ER admission scenario completed: %s", result)
                if result.get("metrics"):
                    await metrics_store.record(result["metrics"])
            except Exception:
                logger.exception("ER admission scenario failed")

    background_tasks.add_task(_run_orchestration)

    return JSONResponse(status_code=202, content={"status": "started", "scenario": "er-admission", "patient_id": patient.id})


@router.post("/scenario/disruption-replan")
async def run_disruption_replan(background_tasks: BackgroundTasks):
    """Trigger the disruption + re-plan scenario.

    Same as ER admission but seeds a second patient and marks a bed as blocked
    to force replanning.
    Returns 202 immediately — orchestration runs as a background task.
    """
    if _scenario_lock.locked():
        return JSONResponse(status_code=409, content={"error": "A scenario is already running"})

    _reset_and_seed()

    now = datetime.now(timezone.utc)

    # Primary patient
    patient1 = Patient(
        id=f"P-{uuid.uuid4().hex[:6].upper()}",
        name="David Park",
        mrn="MRN-20002",
        state=PatientState.AWAITING_BED,
        current_location="ED Bay 1",
        diagnosis="Appendicitis — pre-op",
        acuity_level=4,
        requested_at=now,
    )
    store.patients[patient1.id] = patient1

    # Disrupt: block a previously-READY bed to reduce capacity
    ready_beds = store.get_beds(filter_fn=lambda b: b.state.value == "READY")
    blocked_bed_id = None
    if ready_beds:
        blocked_bed = ready_beds[0]
        blocked_bed_id = blocked_bed.id
        # Direct state set for the disruption seed (not an agent action)
        blocked_bed.state = BedState.BLOCKED
        blocked_bed.last_state_change = now

    await event_store.publish(
        event_type=PATIENT_BED_REQUEST_CREATED,
        entity_id=patient1.id,
        payload={"patient_id": patient1.id, "name": patient1.name, "acuity": patient1.acuity_level, "location": patient1.current_location},
    )

    msg = f"New URGENT bed request for patient {patient1.name} ({patient1.id}) from {patient1.current_location}. Acuity: {patient1.acuity_level}."
    if blocked_bed_id:
        msg += f" NOTE: Bed {blocked_bed_id} just went BLOCKED — capacity reduced."

    await message_store.publish(
        agent_name="bed-coordinator",
        agent_role="Bed Coordinator Assistant",
        content=msg,
        intent_tag=IntentTag.PROPOSE,
    )

    async def _run_orchestration():
        async with _scenario_lock:
            try:
                result = await run_scenario("disruption-replan", store, event_store, message_store)
                logger.info("Disruption-replan scenario completed: %s", result)
                if result.get("metrics"):
                    await metrics_store.record(result["metrics"])
            except Exception:
                logger.exception("Disruption-replan scenario failed")

    background_tasks.add_task(_run_orchestration)

    return JSONResponse(status_code=202, content={"status": "started", "scenario": "disruption-replan", "patient_id": patient1.id, "blocked_bed": blocked_bed_id})


@router.post("/scenario/evs-gated")
async def run_evs_gated(background_tasks: BackgroundTasks):
    """Trigger the EVS-gated placement scenario.

    Best-fit bed is DIRTY — must wait for EVS cleaning before assignment.
    Demonstrates: Discharge → EVS task → room clean → bed READY → assign.
    """
    if _scenario_lock.locked():
        return JSONResponse(status_code=409, content={"error": "A scenario is already running"})

    _reset_and_seed()

    now = datetime.now(timezone.utc)
    patient = Patient(
        id=f"P-{uuid.uuid4().hex[:6].upper()}",
        name="Emily Zhang",
        mrn="MRN-20003",
        state=PatientState.AWAITING_BED,
        current_location="ED Bay 5",
        diagnosis="Pneumonia",
        acuity_level=3,
        admission_source=AdmissionSource.ER,
        requested_at=now,
    )
    store.patients[patient.id] = patient

    await event_store.publish(
        event_type=PATIENT_BED_REQUEST_CREATED,
        entity_id=patient.id,
        payload={"patient_id": patient.id, "name": patient.name, "acuity": patient.acuity_level, "location": patient.current_location, "admission_source": "ER"},
    )

    async def _run_orchestration():
        async with _scenario_lock:
            try:
                result = await run_scenario("evs-gated", store, event_store, message_store)
                logger.info("EVS-gated scenario completed: %s", result)
                if result.get("metrics"):
                    await metrics_store.record(result["metrics"])
            except Exception:
                logger.exception("EVS-gated scenario failed")

    background_tasks.add_task(_run_orchestration)

    return JSONResponse(status_code=202, content={"status": "started", "scenario": "evs-gated", "patient_id": patient.id})


@router.post("/scenario/or-admission")
async def run_or_admission(background_tasks: BackgroundTasks):
    """Trigger an OR (post-surgical) admission scenario.

    A surgical team places an admission order for a post-op patient.
    Demonstrates admission from a non-ER source.
    """
    if _scenario_lock.locked():
        return JSONResponse(status_code=409, content={"error": "A scenario is already running"})

    _reset_and_seed()

    now = datetime.now(timezone.utc)
    patient = Patient(
        id=f"P-{uuid.uuid4().hex[:6].upper()}",
        name="Marcus Rivera",
        mrn="MRN-20004",
        state=PatientState.AWAITING_BED,
        current_location="Recovery Room 2",
        diagnosis="Post-op appendectomy",
        acuity_level=2,
        admission_source=AdmissionSource.OR,
        requested_at=now,
    )
    store.patients[patient.id] = patient

    await event_store.publish(
        event_type=PATIENT_BED_REQUEST_CREATED,
        entity_id=patient.id,
        payload={"patient_id": patient.id, "name": patient.name, "acuity": patient.acuity_level, "location": patient.current_location, "admission_source": "OR"},
    )

    async def _run_orchestration():
        async with _scenario_lock:
            try:
                result = await run_scenario("or-admission", store, event_store, message_store)
                logger.info("OR-admission scenario completed: %s", result)
                if result.get("metrics"):
                    await metrics_store.record(result["metrics"])
            except Exception:
                logger.exception("OR-admission scenario failed")

    background_tasks.add_task(_run_orchestration)

    return JSONResponse(status_code=202, content={"status": "started", "scenario": "or-admission", "patient_id": patient.id})


@router.post("/scenario/unit-transfer")
async def run_unit_transfer(background_tasks: BackgroundTasks):
    """Trigger a unit-to-unit transfer scenario.

    An existing patient needs transfer triggered by a transfer order (not admission).
    Demonstrates transfer workflow with staffing-adjusted capacity.
    """
    if _scenario_lock.locked():
        return JSONResponse(status_code=409, content={"error": "A scenario is already running"})

    _reset_and_seed()

    now = datetime.now(timezone.utc)

    # Use an existing patient who needs transfer — create a new one for clean state
    patient = Patient(
        id=f"P-{uuid.uuid4().hex[:6].upper()}",
        name="Aisha Williams",
        mrn="MRN-20005",
        state=PatientState.AWAITING_BED,
        current_location="5-South 501A",
        diagnosis="CHF exacerbation",
        acuity_level=4,
        admission_source=AdmissionSource.TRANSFER,
        requested_at=now,
    )
    store.patients[patient.id] = patient

    await event_store.publish(
        event_type="TransferOrderCreated",
        entity_id=patient.id,
        payload={"patient_id": patient.id, "name": patient.name, "acuity": patient.acuity_level, "from_location": patient.current_location, "workflow_type": "transfer"},
    )

    async def _run_orchestration():
        async with _scenario_lock:
            try:
                result = await run_scenario("unit-transfer", store, event_store, message_store)
                logger.info("Unit-transfer scenario completed: %s", result)
                if result.get("metrics"):
                    await metrics_store.record(result["metrics"])
            except Exception:
                logger.exception("Unit-transfer scenario failed")

    background_tasks.add_task(_run_orchestration)

    return JSONResponse(status_code=202, content={"status": "started", "scenario": "unit-transfer", "patient_id": patient.id})
