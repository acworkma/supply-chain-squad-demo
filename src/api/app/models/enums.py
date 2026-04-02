"""State enums for the bed-management domain model."""

from enum import StrEnum


class BedState(StrEnum):
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    DIRTY = "DIRTY"
    CLEANING = "CLEANING"
    READY = "READY"
    BLOCKED = "BLOCKED"


class PatientState(StrEnum):
    AWAITING_BED = "AWAITING_BED"
    BED_ASSIGNED = "BED_ASSIGNED"
    TRANSPORT_READY = "TRANSPORT_READY"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    DISCHARGED = "DISCHARGED"


class TaskState(StrEnum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"


class TaskType(StrEnum):
    EVS_CLEANING = "EVS_CLEANING"
    TRANSPORT = "TRANSPORT"
    BED_PREP = "BED_PREP"
    OTHER = "OTHER"


class TransportPriority(StrEnum):
    STAT = "STAT"
    URGENT = "URGENT"
    ROUTINE = "ROUTINE"


class AdmissionSource(StrEnum):
    ER = "ER"
    OR = "OR"
    DIRECT_ADMIT = "DIRECT_ADMIT"
    TRANSFER = "TRANSFER"


class IntentTag(StrEnum):
    PROPOSE = "PROPOSE"
    VALIDATE = "VALIDATE"
    EXECUTE = "EXECUTE"
    ESCALATE = "ESCALATE"
