"""Pydantic v2 entity models for the bed-management domain."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .enums import (
    AdmissionSource,
    BedState,
    IntentTag,
    PatientState,
    TaskState,
    TaskType,
    TransportPriority,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Bed(BaseModel):
    id: str
    unit: str
    room_number: str
    bed_letter: str
    state: BedState = BedState.READY
    patient_id: Optional[str] = None
    reserved_for_patient_id: Optional[str] = None
    reserved_until: Optional[datetime] = None
    last_state_change: datetime = Field(default_factory=_utcnow)


class Patient(BaseModel):
    id: str
    name: str
    mrn: str
    state: PatientState = PatientState.AWAITING_BED
    current_location: str
    assigned_bed_id: Optional[str] = None
    diagnosis: str = ""
    acuity_level: int = Field(default=3, ge=1, le=5)
    admission_source: AdmissionSource = AdmissionSource.ER
    requested_at: datetime = Field(default_factory=_utcnow)
    eta_minutes: Optional[int] = None


class Task(BaseModel):
    id: str
    type: TaskType
    subject_id: str
    state: TaskState = TaskState.CREATED
    priority: TransportPriority = TransportPriority.ROUTINE
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    due_by: Optional[datetime] = None
    notes: str = ""
    eta_minutes: Optional[int] = None


class Transport(BaseModel):
    id: str
    patient_id: str
    from_location: str
    to_location: str
    priority: TransportPriority = TransportPriority.ROUTINE
    state: TaskState = TaskState.CREATED
    scheduled_time: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None


class Reservation(BaseModel):
    id: str
    bed_id: str
    patient_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    hold_until: datetime
    is_active: bool = True


class AgentMessage(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_name: str
    agent_role: str
    content: str
    intent_tag: IntentTag
    related_event_ids: list[str] = Field(default_factory=list)
