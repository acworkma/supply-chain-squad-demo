"""
State machine transition tests — the MOST IMPORTANT tests in the suite.

The state machine is the core invariant of the system (ADR-003). Every state
change must go through a validated transition. These tests exhaustively cover
ALL valid transitions (must succeed) and ALL invalid transitions (must raise
InvalidTransitionError).

Transition maps are taken from app.models.transitions.
"""

import pytest
from itertools import product

from app.models.enums import ScanState, POState, ShipmentState, TaskState
from app.models.transitions import (
    VALID_SCAN_TRANSITIONS,
    VALID_PO_TRANSITIONS,
    VALID_SHIPMENT_TRANSITIONS,
    VALID_TASK_TRANSITIONS,
    validate_transition,
    InvalidTransitionError,
)


# ===================================================================
# SCAN TRANSITIONS
# ===================================================================
#
# From the implementation:
#   INITIATED        → {ANALYZING}
#   ANALYZING        → {ITEMS_IDENTIFIED}
#   ITEMS_IDENTIFIED → {SOURCING}
#   SOURCING         → {ORDERING}
#   ORDERING         → {PENDING_APPROVAL, COMPLETE}
#   PENDING_APPROVAL → {COMPLETE}
#   COMPLETE         → {} (terminal)
#
# Total valid: 1+1+1+1+2+1+0 = 7

EXPECTED_VALID_SCAN: list[tuple[ScanState, ScanState]] = [
    (ScanState.INITIATED, ScanState.ANALYZING),
    (ScanState.ANALYZING, ScanState.ITEMS_IDENTIFIED),
    (ScanState.ITEMS_IDENTIFIED, ScanState.SOURCING),
    (ScanState.SOURCING, ScanState.ORDERING),
    (ScanState.ORDERING, ScanState.PENDING_APPROVAL),
    (ScanState.ORDERING, ScanState.COMPLETE),
    (ScanState.PENDING_APPROVAL, ScanState.COMPLETE),
]

_ALL_SCAN_PAIRS = [
    (f, t) for f, t in product(ScanState, ScanState) if f != t
]

INVALID_SCAN: list[tuple[ScanState, ScanState]] = [
    pair for pair in _ALL_SCAN_PAIRS if pair not in EXPECTED_VALID_SCAN
]


class TestScanTransitions:
    """Exhaustive scan state-machine coverage."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        EXPECTED_VALID_SCAN,
        ids=[f"{f.value}→{t.value}" for f, t in EXPECTED_VALID_SCAN],
    )
    def test_valid_scan_transition_succeeds(self, from_state, to_state):
        validate_transition(from_state, to_state, VALID_SCAN_TRANSITIONS)

    @pytest.mark.parametrize(
        "from_state,to_state",
        INVALID_SCAN,
        ids=[f"{f.value}→{t.value}" for f, t in INVALID_SCAN],
    )
    def test_invalid_scan_transition_raises(self, from_state, to_state):
        with pytest.raises(InvalidTransitionError):
            validate_transition(from_state, to_state, VALID_SCAN_TRANSITIONS)

    def test_self_transition_is_noop_or_rejected(self):
        for state in ScanState:
            try:
                validate_transition(state, state, VALID_SCAN_TRANSITIONS)
            except InvalidTransitionError:
                pass

    def test_valid_transition_count(self):
        assert len(EXPECTED_VALID_SCAN) == 7

    def test_invalid_transition_count(self):
        # 7 states × 6 non-self = 42 pairs, minus 7 valid = 35 invalid
        assert len(INVALID_SCAN) == 35

    def test_complete_is_terminal(self):
        """COMPLETE has no outgoing transitions."""
        for target in ScanState:
            if target == ScanState.COMPLETE:
                continue
            with pytest.raises(InvalidTransitionError):
                validate_transition(ScanState.COMPLETE,
                                    target, VALID_SCAN_TRANSITIONS)

    def test_initiated_is_entry_point(self):
        """INITIATED can only go to ANALYZING."""
        for target in ScanState:
            if target == ScanState.INITIATED:
                continue
            if target == ScanState.ANALYZING:
                validate_transition(ScanState.INITIATED,
                                    target, VALID_SCAN_TRANSITIONS)
            else:
                with pytest.raises(InvalidTransitionError):
                    validate_transition(ScanState.INITIATED,
                                        target, VALID_SCAN_TRANSITIONS)

    def test_ordering_can_skip_approval(self):
        """ORDERING → COMPLETE is valid (auto-approved path)."""
        validate_transition(ScanState.ORDERING,
                            ScanState.COMPLETE, VALID_SCAN_TRANSITIONS)

    def test_ordering_can_go_to_pending_approval(self):
        """ORDERING → PENDING_APPROVAL for human approval path."""
        validate_transition(ScanState.ORDERING,
                            ScanState.PENDING_APPROVAL, VALID_SCAN_TRANSITIONS)


# ===================================================================
# PURCHASE ORDER TRANSITIONS
# ===================================================================
#
# From the implementation:
#   CREATED          → {PENDING_APPROVAL, APPROVED}
#   PENDING_APPROVAL → {APPROVED, CANCELLED}
#   APPROVED         → {SUBMITTED}
#   SUBMITTED        → {CONFIRMED}
#   CONFIRMED        → {SHIPPED}
#   SHIPPED          → {RECEIVED}
#   RECEIVED         → {} (terminal)
#   CANCELLED        → {} (terminal)
#
# Total valid: 2+2+1+1+1+1+0+0 = 8

EXPECTED_VALID_PO: list[tuple[POState, POState]] = [
    (POState.CREATED, POState.PENDING_APPROVAL),
    (POState.CREATED, POState.APPROVED),
    (POState.PENDING_APPROVAL, POState.APPROVED),
    (POState.PENDING_APPROVAL, POState.CANCELLED),
    (POState.APPROVED, POState.SUBMITTED),
    (POState.SUBMITTED, POState.CONFIRMED),
    (POState.CONFIRMED, POState.SHIPPED),
    (POState.SHIPPED, POState.RECEIVED),
]

_ALL_PO_PAIRS = [
    (f, t) for f, t in product(POState, POState) if f != t
]

INVALID_PO: list[tuple[POState, POState]] = [
    pair for pair in _ALL_PO_PAIRS if pair not in EXPECTED_VALID_PO
]


class TestPOTransitions:
    """Exhaustive purchase order state-machine coverage."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        EXPECTED_VALID_PO,
        ids=[f"{f.value}→{t.value}" for f, t in EXPECTED_VALID_PO],
    )
    def test_valid_po_transition_succeeds(self, from_state, to_state):
        validate_transition(from_state, to_state, VALID_PO_TRANSITIONS)

    @pytest.mark.parametrize(
        "from_state,to_state",
        INVALID_PO,
        ids=[f"{f.value}→{t.value}" for f, t in INVALID_PO],
    )
    def test_invalid_po_transition_raises(self, from_state, to_state):
        with pytest.raises(InvalidTransitionError):
            validate_transition(from_state, to_state, VALID_PO_TRANSITIONS)

    def test_self_transition_is_noop_or_rejected(self):
        for state in POState:
            try:
                validate_transition(state, state, VALID_PO_TRANSITIONS)
            except InvalidTransitionError:
                pass

    def test_valid_transition_count(self):
        assert len(EXPECTED_VALID_PO) == 8

    def test_invalid_transition_count(self):
        # 8 states × 7 non-self = 56 pairs, minus 8 valid = 48 invalid
        assert len(INVALID_PO) == 48

    def test_received_is_terminal(self):
        """RECEIVED has no outgoing transitions."""
        for target in POState:
            if target == POState.RECEIVED:
                continue
            with pytest.raises(InvalidTransitionError):
                validate_transition(
                    POState.RECEIVED, target, VALID_PO_TRANSITIONS)

    def test_cancelled_is_terminal(self):
        """CANCELLED has no outgoing transitions."""
        for target in POState:
            if target == POState.CANCELLED:
                continue
            with pytest.raises(InvalidTransitionError):
                validate_transition(POState.CANCELLED,
                                    target, VALID_PO_TRANSITIONS)

    def test_created_can_be_auto_approved(self):
        """CREATED → APPROVED (auto-approval path)."""
        validate_transition(
            POState.CREATED, POState.APPROVED, VALID_PO_TRANSITIONS)

    def test_created_can_go_to_pending_approval(self):
        """CREATED → PENDING_APPROVAL (human approval path)."""
        validate_transition(
            POState.CREATED, POState.PENDING_APPROVAL, VALID_PO_TRANSITIONS)

    def test_pending_approval_can_be_cancelled(self):
        """PENDING_APPROVAL → CANCELLED (human rejection)."""
        validate_transition(POState.PENDING_APPROVAL,
                            POState.CANCELLED, VALID_PO_TRANSITIONS)

    def test_cannot_cancel_after_approved(self):
        """Cannot cancel once APPROVED, SUBMITTED, CONFIRMED, SHIPPED, or RECEIVED."""
        for state in [POState.APPROVED, POState.SUBMITTED, POState.CONFIRMED, POState.SHIPPED, POState.RECEIVED]:
            with pytest.raises(InvalidTransitionError):
                validate_transition(
                    state, POState.CANCELLED, VALID_PO_TRANSITIONS)


# ===================================================================
# SHIPMENT TRANSITIONS
# ===================================================================
#
# From the implementation:
#   CREATED    → {SHIPPED}
#   SHIPPED    → {IN_TRANSIT, DELAYED}
#   IN_TRANSIT → {DELIVERED, DELAYED}
#   DELAYED    → {IN_TRANSIT, DELIVERED}
#   DELIVERED  → {} (terminal)
#
# Total valid: 1+2+2+2+0 = 7

EXPECTED_VALID_SHIPMENT: list[tuple[ShipmentState, ShipmentState]] = [
    (ShipmentState.CREATED, ShipmentState.SHIPPED),
    (ShipmentState.SHIPPED, ShipmentState.IN_TRANSIT),
    (ShipmentState.SHIPPED, ShipmentState.DELAYED),
    (ShipmentState.IN_TRANSIT, ShipmentState.DELIVERED),
    (ShipmentState.IN_TRANSIT, ShipmentState.DELAYED),
    (ShipmentState.DELAYED, ShipmentState.IN_TRANSIT),
    (ShipmentState.DELAYED, ShipmentState.DELIVERED),
]

_ALL_SHIPMENT_PAIRS = [
    (f, t) for f, t in product(ShipmentState, ShipmentState) if f != t
]

INVALID_SHIPMENT: list[tuple[ShipmentState, ShipmentState]] = [
    pair for pair in _ALL_SHIPMENT_PAIRS if pair not in EXPECTED_VALID_SHIPMENT
]


class TestShipmentTransitions:
    """Exhaustive shipment state-machine coverage."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        EXPECTED_VALID_SHIPMENT,
        ids=[f"{f.value}→{t.value}" for f, t in EXPECTED_VALID_SHIPMENT],
    )
    def test_valid_shipment_transition_succeeds(self, from_state, to_state):
        validate_transition(from_state, to_state, VALID_SHIPMENT_TRANSITIONS)

    @pytest.mark.parametrize(
        "from_state,to_state",
        INVALID_SHIPMENT,
        ids=[f"{f.value}→{t.value}" for f, t in INVALID_SHIPMENT],
    )
    def test_invalid_shipment_transition_raises(self, from_state, to_state):
        with pytest.raises(InvalidTransitionError):
            validate_transition(from_state, to_state,
                                VALID_SHIPMENT_TRANSITIONS)

    def test_self_transition_is_noop_or_rejected(self):
        for state in ShipmentState:
            try:
                validate_transition(state, state, VALID_SHIPMENT_TRANSITIONS)
            except InvalidTransitionError:
                pass

    def test_valid_transition_count(self):
        assert len(EXPECTED_VALID_SHIPMENT) == 7

    def test_invalid_transition_count(self):
        # 5 states × 4 non-self = 20 pairs, minus 7 valid = 13 invalid
        assert len(INVALID_SHIPMENT) == 13

    def test_delivered_is_terminal(self):
        """DELIVERED has no outgoing transitions."""
        for target in ShipmentState:
            if target == ShipmentState.DELIVERED:
                continue
            with pytest.raises(InvalidTransitionError):
                validate_transition(ShipmentState.DELIVERED,
                                    target, VALID_SHIPMENT_TRANSITIONS)

    def test_delayed_can_resume_or_deliver(self):
        """DELAYED → IN_TRANSIT (resume) or DELAYED → DELIVERED."""
        validate_transition(ShipmentState.DELAYED,
                            ShipmentState.IN_TRANSIT, VALID_SHIPMENT_TRANSITIONS)
        validate_transition(ShipmentState.DELAYED,
                            ShipmentState.DELIVERED, VALID_SHIPMENT_TRANSITIONS)

    def test_delayed_reachable_from_shipped_and_in_transit(self):
        """DELAYED can be reached from SHIPPED and IN_TRANSIT."""
        validate_transition(ShipmentState.SHIPPED,
                            ShipmentState.DELAYED, VALID_SHIPMENT_TRANSITIONS)
        validate_transition(ShipmentState.IN_TRANSIT,
                            ShipmentState.DELAYED, VALID_SHIPMENT_TRANSITIONS)


# ===================================================================
# TASK TRANSITIONS (unchanged from previous domain)
# ===================================================================
#
# From the implementation:
#   CREATED     → {ACCEPTED, CANCELLED}
#   ACCEPTED    → {IN_PROGRESS}
#   IN_PROGRESS → {COMPLETED, ESCALATED}
#   ESCALATED   → {IN_PROGRESS, CANCELLED}
#   COMPLETED   → {} (terminal)
#   CANCELLED   → {} (terminal)
#
# Total valid: 2+1+2+2+0+0 = 7

EXPECTED_VALID_TASK: list[tuple[TaskState, TaskState]] = [
    (TaskState.CREATED, TaskState.ACCEPTED),
    (TaskState.CREATED, TaskState.CANCELLED),
    (TaskState.ACCEPTED, TaskState.IN_PROGRESS),
    (TaskState.IN_PROGRESS, TaskState.COMPLETED),
    (TaskState.IN_PROGRESS, TaskState.ESCALATED),
    (TaskState.ESCALATED, TaskState.IN_PROGRESS),
    (TaskState.ESCALATED, TaskState.CANCELLED),
]

_ALL_TASK_PAIRS = [
    (f, t) for f, t in product(TaskState, TaskState) if f != t
]

INVALID_TASK: list[tuple[TaskState, TaskState]] = [
    pair for pair in _ALL_TASK_PAIRS if pair not in EXPECTED_VALID_TASK
]


class TestTaskTransitions:
    """Exhaustive task state-machine coverage (unchanged from previous domain)."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        EXPECTED_VALID_TASK,
        ids=[f"{f.value}→{t.value}" for f, t in EXPECTED_VALID_TASK],
    )
    def test_valid_task_transition_succeeds(self, from_state, to_state):
        validate_transition(from_state, to_state, VALID_TASK_TRANSITIONS)

    @pytest.mark.parametrize(
        "from_state,to_state",
        INVALID_TASK,
        ids=[f"{f.value}→{t.value}" for f, t in INVALID_TASK],
    )
    def test_invalid_task_transition_raises(self, from_state, to_state):
        with pytest.raises(InvalidTransitionError):
            validate_transition(from_state, to_state, VALID_TASK_TRANSITIONS)

    def test_valid_transition_count(self):
        assert len(EXPECTED_VALID_TASK) == 7

    def test_invalid_transition_count(self):
        # 6 × 5 = 30 minus 7 valid = 23 invalid
        assert len(INVALID_TASK) == 23

    def test_completed_is_terminal(self):
        """COMPLETED has no outgoing transitions."""
        for target in TaskState:
            if target == TaskState.COMPLETED:
                continue
            with pytest.raises(InvalidTransitionError):
                validate_transition(TaskState.COMPLETED,
                                    target, VALID_TASK_TRANSITIONS)

    def test_cancelled_is_terminal(self):
        """CANCELLED has no outgoing transitions."""
        for target in TaskState:
            if target == TaskState.CANCELLED:
                continue
            with pytest.raises(InvalidTransitionError):
                validate_transition(TaskState.CANCELLED,
                                    target, VALID_TASK_TRANSITIONS)

    def test_escalated_can_resume_or_cancel(self):
        """ESCALATED → IN_PROGRESS (resume) and ESCALATED → CANCELLED."""
        validate_transition(TaskState.ESCALATED,
                            TaskState.IN_PROGRESS, VALID_TASK_TRANSITIONS)
        validate_transition(TaskState.ESCALATED,
                            TaskState.CANCELLED, VALID_TASK_TRANSITIONS)

    def test_accepted_cannot_cancel_directly(self):
        """ACCEPTED can only go to IN_PROGRESS (no direct cancel)."""
        with pytest.raises(InvalidTransitionError):
            validate_transition(TaskState.ACCEPTED,
                                TaskState.CANCELLED, VALID_TASK_TRANSITIONS)
