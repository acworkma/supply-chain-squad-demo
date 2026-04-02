"""Event type definitions and the base Event model."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Event-type string constants (spec §8) ──────────────────────────
PATIENT_BED_REQUEST_CREATED = "PatientBedRequestCreated"
PREDICTION_GENERATED = "PredictionGenerated"
ASSIGNMENT_VALIDATED = "AssignmentValidated"
BED_RESERVED = "BedReserved"
FALLBACK_PLAN_SET = "FallbackPlanSet"
EVS_TASK_CREATED = "EVSTaskCreated"
EVS_TASK_STATUS_CHANGED = "EVSTaskStatusChanged"
BED_STATE_CHANGED = "BedStateChanged"
TRANSPORT_SCHEDULED = "TransportScheduled"
TRANSPORT_STARTED = "TransportStarted"
TRANSPORT_COMPLETED = "TransportCompleted"
PATIENT_STATE_CHANGED = "PatientStateChanged"
SLA_RISK_DETECTED = "SlaRiskDetected"
RESERVATION_RELEASED = "ReservationReleased"
TRANSPORT_RESCHEDULED = "TransportRescheduled"


class StateDiff(BaseModel):
    from_state: str
    to_state: str


class Event(BaseModel):
    """Immutable event appended to the event store."""

    id: str
    sequence: int = 0
    timestamp: datetime = Field(default_factory=_utcnow)
    event_type: str
    entity_id: str
    payload: dict = Field(default_factory=dict)
    state_diff: Optional[StateDiff] = None
