"""State-machine transition validation for beds, patients, and tasks."""

from .enums import BedState, PatientState, TaskState


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed by the state machine."""

    def __init__(self, entity_type: str, current: str, target: str) -> None:
        self.entity_type = entity_type
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid {entity_type} transition: {current} → {target}"
        )


# ── Bed state machine ──────────────────────────────────────────────
VALID_BED_TRANSITIONS: dict[BedState, set[BedState]] = {
    BedState.OCCUPIED: {BedState.DIRTY, BedState.BLOCKED},
    BedState.DIRTY: {BedState.CLEANING, BedState.BLOCKED},
    BedState.CLEANING: {BedState.READY, BedState.BLOCKED},
    BedState.READY: {BedState.RESERVED, BedState.OCCUPIED, BedState.BLOCKED},
    BedState.RESERVED: {BedState.OCCUPIED, BedState.READY, BedState.BLOCKED},
    BedState.BLOCKED: {BedState.DIRTY},
}

# ── Patient state machine ──────────────────────────────────────────
VALID_PATIENT_TRANSITIONS: dict[PatientState, set[PatientState]] = {
    PatientState.AWAITING_BED: {PatientState.BED_ASSIGNED},
    PatientState.BED_ASSIGNED: {PatientState.TRANSPORT_READY, PatientState.AWAITING_BED},
    PatientState.TRANSPORT_READY: {PatientState.IN_TRANSIT},
    PatientState.IN_TRANSIT: {PatientState.ARRIVED},
    PatientState.ARRIVED: {PatientState.DISCHARGED},
    PatientState.DISCHARGED: set(),
}

# ── Task state machine ─────────────────────────────────────────────
VALID_TASK_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.CREATED: {TaskState.ACCEPTED, TaskState.CANCELLED},
    TaskState.ACCEPTED: {TaskState.IN_PROGRESS},
    TaskState.IN_PROGRESS: {TaskState.COMPLETED, TaskState.ESCALATED},
    TaskState.ESCALATED: {TaskState.IN_PROGRESS, TaskState.CANCELLED},
    TaskState.COMPLETED: set(),
    TaskState.CANCELLED: set(),
}


def validate_transition(
    current: BedState | PatientState | TaskState,
    target: BedState | PatientState | TaskState,
    valid_map: dict,
) -> None:
    """Validate that *current* → *target* is a legal transition.

    Raises ``InvalidTransitionError`` when the transition is not in *valid_map*.
    """
    if isinstance(current, BedState):
        entity_type = "bed"
    elif isinstance(current, PatientState):
        entity_type = "patient"
    elif isinstance(current, TaskState):
        entity_type = "task"
    else:
        entity_type = "unknown"

    allowed = valid_map.get(current)
    if allowed is None or target not in allowed:
        raise InvalidTransitionError(entity_type, str(current), str(target))
