"""Deterministic tool functions — the ONLY way agents change state (ADR-003).

Each function takes the three stores as arguments, validates inputs,
mutates state via the StateStore transition helpers, emits events, and
publishes agent messages. Returns a structured dict result.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..events.event_store import EventStore
from ..messages.message_store import MessageStore
from ..models.entities import Reservation, Task, Transport
from ..models.enums import (
    BedState,
    IntentTag,
    PatientState,
    TaskState,
    TaskType,
    TransportPriority,
)
from ..models.events import (
    BED_RESERVED,
    BED_STATE_CHANGED,
    EVS_TASK_CREATED,
    EVS_TASK_STATUS_CHANGED,
    RESERVATION_RELEASED,
    SLA_RISK_DETECTED,
    TRANSPORT_SCHEDULED,
)
from ..state.store import StateStore, get_unit_for_diagnosis, get_campus_for_unit


# ── Read-only tools ─────────────────────────────────────────────────

async def get_patient(
    patient_id: str,
    *,
    state_store: StateStore,
    **_kwargs,
) -> dict:
    """Look up a single patient by ID."""
    patient = state_store.get_patient(patient_id)
    if patient is None:
        return {"ok": False, "error": f"Patient {patient_id} not found"}
    return {"ok": True, "patient": patient.model_dump(mode="json")}


async def get_beds(
    *,
    state_store: StateStore,
    unit: Optional[str] = None,
    state: Optional[str] = None,
    diagnosis: Optional[str] = None,
    **_kwargs,
) -> dict:
    """List beds, optionally filtered by unit, state, and/or diagnosis-appropriate units."""
    # If diagnosis is provided, determine clinically appropriate units
    allowed_units: list[str] | None = None
    if diagnosis:
        allowed_units = get_unit_for_diagnosis(diagnosis)

    def _filter(b):
        if unit and b.unit != unit:
            return False
        if state and b.state != state:
            return False
        if allowed_units is not None and b.unit not in allowed_units:
            return False
        return True

    beds = state_store.get_beds(filter_fn=_filter)
    return {"ok": True, "beds": [b.model_dump(mode="json") for b in beds]}


async def get_tasks(
    *,
    state_store: StateStore,
    task_state: Optional[str] = None,
    task_type: Optional[str] = None,
    **_kwargs,
) -> dict:
    """List tasks, optionally filtered by state and/or type."""
    def _filter(t):
        if task_state and t.state != task_state:
            return False
        if task_type and t.type != task_type:
            return False
        return True

    tasks = state_store.get_tasks(filter_fn=_filter)
    return {"ok": True, "tasks": [t.model_dump(mode="json") for t in tasks]}


# ── Bed reservation ─────────────────────────────────────────────────

async def reserve_bed(
    bed_id: str,
    patient_id: str,
    hold_minutes: int = 30,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Transition bed to RESERVED, create a reservation, emit BedReserved."""
    bed = state_store.get_bed(bed_id)
    if bed is None:
        return {"ok": False, "error": f"Bed {bed_id} not found"}
    patient = state_store.get_patient(patient_id)
    if patient is None:
        return {"ok": False, "error": f"Patient {patient_id} not found"}

    old_state = bed.state
    try:
        await state_store.transition_bed(bed_id, BedState.RESERVED)
    except (KeyError, Exception) as exc:
        return {"ok": False, "error": str(exc)}

    # Update bed metadata
    bed.reserved_for_patient_id = patient_id
    hold_until = datetime.now(timezone.utc) + timedelta(minutes=hold_minutes)
    bed.reserved_until = hold_until

    reservation_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
    reservation = Reservation(
        id=reservation_id,
        bed_id=bed_id,
        patient_id=patient_id,
        hold_until=hold_until,
    )
    state_store.reservations[reservation_id] = reservation

    event = await event_store.publish(
        event_type=BED_RESERVED,
        entity_id=bed_id,
        payload={"bed_id": bed_id, "patient_id": patient_id, "reservation_id": reservation_id, "hold_minutes": hold_minutes},
        state_diff={"from_state": str(old_state), "to_state": str(BedState.RESERVED)},
    )

    await message_store.publish(
        agent_name="bed-allocation",
        agent_role="Bed Allocation Agent",
        content=f"Reserved bed {bed_id} for patient {patient_id} (hold {hold_minutes} min).",
        intent_tag=IntentTag.EXECUTE,
        related_event_ids=[event.id],
    )

    return {
        "ok": True,
        "reservation_id": reservation_id,
        "bed_id": bed_id,
        "patient_id": patient_id,
        "hold_until": hold_until.isoformat(),
    }


async def release_bed_reservation(
    bed_id: str,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Deactivate reservation, transition bed back to READY, emit ReservationReleased."""
    bed = state_store.get_bed(bed_id)
    if bed is None:
        return {"ok": False, "error": f"Bed {bed_id} not found"}

    # Find active reservation for this bed
    active = [r for r in state_store.reservations.values() if r.bed_id == bed_id and r.is_active]
    for r in active:
        r.is_active = False

    old_state = bed.state
    try:
        await state_store.transition_bed(bed_id, BedState.READY)
    except (KeyError, Exception) as exc:
        return {"ok": False, "error": str(exc)}

    bed.reserved_for_patient_id = None
    bed.reserved_until = None

    event = await event_store.publish(
        event_type=RESERVATION_RELEASED,
        entity_id=bed_id,
        payload={"bed_id": bed_id, "released_reservations": [r.id for r in active]},
        state_diff={"from_state": str(old_state), "to_state": str(BedState.READY)},
    )

    await message_store.publish(
        agent_name="bed-allocation",
        agent_role="Bed Allocation Agent",
        content=f"Released reservation on bed {bed_id}.",
        intent_tag=IntentTag.EXECUTE,
        related_event_ids=[event.id],
    )

    return {"ok": True, "bed_id": bed_id, "released_reservations": [r.id for r in active]}


# ── Task management ─────────────────────────────────────────────────

async def create_task(
    task_type: str,
    subject_id: str,
    priority: str = "ROUTINE",
    due_by: Optional[str] = None,
    notes: str = "",
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Create a new task, emit EVSTaskCreated (or generic task event)."""
    task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
    parsed_due = datetime.fromisoformat(due_by) if due_by else None

    task = Task(
        id=task_id,
        type=TaskType(task_type),
        subject_id=subject_id,
        state=TaskState.CREATED,
        priority=TransportPriority(priority),
        due_by=parsed_due,
        notes=notes,
    )
    state_store.tasks[task_id] = task

    event_type = EVS_TASK_CREATED if task_type == TaskType.EVS_CLEANING else EVS_TASK_CREATED
    event = await event_store.publish(
        event_type=event_type,
        entity_id=task_id,
        payload={"task_id": task_id, "type": task_type, "subject_id": subject_id, "priority": priority},
    )

    agent_name = "evs-tasking" if task_type == TaskType.EVS_CLEANING else "bed-coordinator"
    await message_store.publish(
        agent_name=agent_name,
        agent_role="EVS Tasking Agent" if task_type == TaskType.EVS_CLEANING else "Bed Coordinator Assistant",
        content=f"Created {task_type} task {task_id} for {subject_id} (priority: {priority}).",
        intent_tag=IntentTag.EXECUTE,
        related_event_ids=[event.id],
    )

    return {"ok": True, "task_id": task_id, "type": task_type, "subject_id": subject_id}


async def update_task(
    task_id: str,
    new_status: str,
    eta_minutes: Optional[int] = None,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Transition task state, optionally update ETA, emit EVSTaskStatusChanged."""
    task = state_store.get_task(task_id)
    if task is None:
        return {"ok": False, "error": f"Task {task_id} not found"}

    old_state = task.state
    new_state = TaskState(new_status)

    try:
        await state_store.transition_task(task_id, new_state)
    except (KeyError, Exception) as exc:
        return {"ok": False, "error": str(exc)}

    if eta_minutes is not None:
        task.eta_minutes = eta_minutes
    if new_state == TaskState.ACCEPTED:
        task.accepted_at = datetime.now(timezone.utc)
    elif new_state == TaskState.COMPLETED:
        task.completed_at = datetime.now(timezone.utc)

    event = await event_store.publish(
        event_type=EVS_TASK_STATUS_CHANGED,
        entity_id=task_id,
        payload={"task_id": task_id, "type": str(task.type), "eta_minutes": eta_minutes},
        state_diff={"from_state": str(old_state), "to_state": str(new_state)},
    )

    await message_store.publish(
        agent_name="evs-tasking",
        agent_role="EVS Tasking Agent",
        content=f"Task {task_id} transitioned {old_state} → {new_state}.",
        intent_tag=IntentTag.EXECUTE,
        related_event_ids=[event.id],
    )

    return {"ok": True, "task_id": task_id, "old_state": str(old_state), "new_state": str(new_state)}


# ── Transport ───────────────────────────────────────────────────────

async def schedule_transport(
    patient_id: str,
    from_location: str,
    to_location: str,
    priority: str = "ROUTINE",
    earliest_time: Optional[str] = None,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Create a transport record, emit TransportScheduled."""
    patient = state_store.get_patient(patient_id)
    if patient is None:
        return {"ok": False, "error": f"Patient {patient_id} not found"}

    transport_id = f"TRN-{uuid.uuid4().hex[:8].upper()}"
    scheduled_time = datetime.fromisoformat(earliest_time) if earliest_time else None

    transport = Transport(
        id=transport_id,
        patient_id=patient_id,
        from_location=from_location,
        to_location=to_location,
        priority=TransportPriority(priority),
        state=TaskState.CREATED,
        scheduled_time=scheduled_time,
    )
    state_store.transports[transport_id] = transport

    event = await event_store.publish(
        event_type=TRANSPORT_SCHEDULED,
        entity_id=transport_id,
        payload={
            "transport_id": transport_id,
            "patient_id": patient_id,
            "from": from_location,
            "to": to_location,
            "priority": priority,
        },
    )

    await message_store.publish(
        agent_name="transport-ops",
        agent_role="Transport Operations Agent",
        content=f"Scheduled transport {transport_id} for patient {patient_id}: {from_location} → {to_location} ({priority}).",
        intent_tag=IntentTag.EXECUTE,
        related_event_ids=[event.id],
    )

    return {"ok": True, "transport_id": transport_id, "patient_id": patient_id}


# ── Generic event emission ──────────────────────────────────────────

async def publish_event(
    event_type: str,
    entity_id: str,
    payload: Optional[dict] = None,
    *,
    event_store: EventStore,
    **_kwargs,
) -> dict:
    """Emit a generic event."""
    event = await event_store.publish(
        event_type=event_type,
        entity_id=entity_id,
        payload=payload or {},
    )
    return {"ok": True, "event_id": event.id, "sequence": event.sequence}


# ── Escalation ──────────────────────────────────────────────────────

async def escalate(
    issue_type: str,
    entity_id: str,
    severity: str,
    message: str,
    *,
    event_store: EventStore,
    message_store: MessageStore,
    **_kwargs,
) -> dict:
    """Emit an SlaRiskDetected event and publish an escalation message."""
    event = await event_store.publish(
        event_type=SLA_RISK_DETECTED,
        entity_id=entity_id,
        payload={"issue_type": issue_type, "severity": severity, "message": message},
    )

    await message_store.publish(
        agent_name="policy-safety",
        agent_role="Policy & Safety Agent",
        content=f"ESCALATION [{severity}]: {issue_type} — {message} (entity: {entity_id})",
        intent_tag=IntentTag.ESCALATE,
        related_event_ids=[event.id],
    )

    return {"ok": True, "event_id": event.id, "issue_type": issue_type, "severity": severity}
