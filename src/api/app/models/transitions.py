"""State-machine transition validation for scans, purchase orders, shipments, and tasks."""

from .enums import POState, ScanState, ShipmentState, TaskState


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed by the state machine."""

    def __init__(self, entity_type: str, current: str, target: str) -> None:
        self.entity_type = entity_type
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid {entity_type} transition: {current} → {target}"
        )


# ── Scan state machine ─────────────────────────────────────────────
VALID_SCAN_TRANSITIONS: dict[ScanState, set[ScanState]] = {
    ScanState.INITIATED:        {ScanState.ANALYZING},
    ScanState.ANALYZING:        {ScanState.ITEMS_IDENTIFIED},
    ScanState.ITEMS_IDENTIFIED: {ScanState.SOURCING},
    ScanState.SOURCING:         {ScanState.ORDERING},
    ScanState.ORDERING:         {ScanState.PENDING_APPROVAL, ScanState.COMPLETE},
    ScanState.PENDING_APPROVAL: {ScanState.COMPLETE},
    ScanState.COMPLETE:         set(),
}

# ── Purchase order state machine ───────────────────────────────────
VALID_PO_TRANSITIONS: dict[POState, set[POState]] = {
    POState.CREATED:          {POState.PENDING_APPROVAL, POState.APPROVED},
    POState.PENDING_APPROVAL: {POState.APPROVED, POState.CANCELLED},
    POState.APPROVED:         {POState.SUBMITTED},
    POState.SUBMITTED:        {POState.CONFIRMED},
    POState.CONFIRMED:        {POState.SHIPPED},
    POState.SHIPPED:          {POState.RECEIVED},
    POState.RECEIVED:         set(),
    POState.CANCELLED:        set(),
}

# ── Shipment state machine ─────────────────────────────────────────
VALID_SHIPMENT_TRANSITIONS: dict[ShipmentState, set[ShipmentState]] = {
    ShipmentState.CREATED:    {ShipmentState.SHIPPED},
    ShipmentState.SHIPPED:    {ShipmentState.IN_TRANSIT, ShipmentState.DELAYED},
    ShipmentState.IN_TRANSIT: {ShipmentState.DELIVERED, ShipmentState.DELAYED},
    ShipmentState.DELAYED:    {ShipmentState.IN_TRANSIT, ShipmentState.DELIVERED},
    ShipmentState.DELIVERED:  set(),
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
    current: ScanState | POState | ShipmentState | TaskState,
    target: ScanState | POState | ShipmentState | TaskState,
    valid_map: dict,
) -> None:
    """Validate that *current* → *target* is a legal transition.

    Raises ``InvalidTransitionError`` when the transition is not in *valid_map*.
    """
    if isinstance(current, ScanState):
        entity_type = "scan"
    elif isinstance(current, POState):
        entity_type = "purchase_order"
    elif isinstance(current, ShipmentState):
        entity_type = "shipment"
    elif isinstance(current, TaskState):
        entity_type = "task"
    else:
        entity_type = "unknown"

    allowed = valid_map.get(current)
    if allowed is None or target not in allowed:
        raise InvalidTransitionError(entity_type, str(current), str(target))
