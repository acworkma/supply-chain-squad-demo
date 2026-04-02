"""
State machine transition tests — the MOST IMPORTANT tests in the suite.

The state machine is the core invariant of the system (ADR-003). Every state
change must go through a validated transition. These tests exhaustively cover
ALL valid transitions (must succeed) and ALL invalid transitions (must raise
InvalidTransitionError).

Transition maps are taken from app.models.transitions (Goose's WI-002).
"""

import pytest
from itertools import product

from app.models.enums import BedState, PatientState, TaskState
from app.models.transitions import (
    VALID_BED_TRANSITIONS,
    VALID_PATIENT_TRANSITIONS,
    VALID_TASK_TRANSITIONS,
    validate_transition,
    InvalidTransitionError,
)


# ===================================================================
# BED TRANSITIONS
# ===================================================================
#
# From the implementation:
#   OCCUPIED  → {DIRTY, BLOCKED}
#   DIRTY     → {CLEANING, BLOCKED}
#   CLEANING  → {READY, BLOCKED}
#   READY     → {RESERVED, OCCUPIED, BLOCKED}
#   RESERVED  → {OCCUPIED, READY, BLOCKED}
#   BLOCKED   → {DIRTY}
#
# Total valid: 2+2+2+3+3+1 = 13

EXPECTED_VALID_BED: list[tuple[BedState, BedState]] = [
    (BedState.OCCUPIED, BedState.DIRTY),
    (BedState.OCCUPIED, BedState.BLOCKED),
    (BedState.DIRTY, BedState.CLEANING),
    (BedState.DIRTY, BedState.BLOCKED),
    (BedState.CLEANING, BedState.READY),
    (BedState.CLEANING, BedState.BLOCKED),
    (BedState.READY, BedState.RESERVED),
    (BedState.READY, BedState.OCCUPIED),
    (BedState.READY, BedState.BLOCKED),
    (BedState.RESERVED, BedState.OCCUPIED),
    (BedState.RESERVED, BedState.READY),
    (BedState.RESERVED, BedState.BLOCKED),
    (BedState.BLOCKED, BedState.DIRTY),
]

_ALL_BED_PAIRS = [
    (f, t) for f, t in product(BedState, BedState) if f != t
]

INVALID_BED: list[tuple[BedState, BedState]] = [
    pair for pair in _ALL_BED_PAIRS if pair not in EXPECTED_VALID_BED
]


class TestBedTransitions:
    """Exhaustive bed state-machine coverage."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        EXPECTED_VALID_BED,
        ids=[f"{f.value}→{t.value}" for f, t in EXPECTED_VALID_BED],
    )
    def test_valid_bed_transition_succeeds(self, from_state, to_state):
        # Should not raise
        validate_transition(from_state, to_state, VALID_BED_TRANSITIONS)

    @pytest.mark.parametrize(
        "from_state,to_state",
        INVALID_BED,
        ids=[f"{f.value}→{t.value}" for f, t in INVALID_BED],
    )
    def test_invalid_bed_transition_raises(self, from_state, to_state):
        with pytest.raises(InvalidTransitionError):
            validate_transition(from_state, to_state, VALID_BED_TRANSITIONS)

    def test_self_transition_is_noop_or_rejected(self):
        """Self-transitions (e.g., READY → READY) should either be no-op or raise."""
        for state in BedState:
            try:
                validate_transition(state, state, VALID_BED_TRANSITIONS)
            except InvalidTransitionError:
                pass  # Also acceptable

    def test_valid_transition_count(self):
        assert len(EXPECTED_VALID_BED) == 13

    def test_invalid_transition_count(self):
        # 6 states × 5 non-self = 30 pairs, minus 13 valid = 17 invalid
        assert len(INVALID_BED) == 17

    def test_every_state_can_reach_blocked(self):
        """Every non-BLOCKED state has a path to BLOCKED (emergency block)."""
        for state in BedState:
            if state == BedState.BLOCKED:
                continue
            # Should not raise
            validate_transition(state, BedState.BLOCKED, VALID_BED_TRANSITIONS)

    def test_blocked_can_only_go_to_dirty(self):
        """BLOCKED → DIRTY is the only exit from blocked."""
        for target in BedState:
            if target == BedState.BLOCKED:
                continue
            if target == BedState.DIRTY:
                validate_transition(BedState.BLOCKED, target, VALID_BED_TRANSITIONS)
            else:
                with pytest.raises(InvalidTransitionError):
                    validate_transition(BedState.BLOCKED, target, VALID_BED_TRANSITIONS)


# ===================================================================
# PATIENT TRANSITIONS
# ===================================================================
#
# From the implementation:
#   AWAITING_BED    → {BED_ASSIGNED}
#   BED_ASSIGNED    → {TRANSPORT_READY, AWAITING_BED}
#   TRANSPORT_READY → {IN_TRANSIT}
#   IN_TRANSIT      → {ARRIVED}
#   ARRIVED         → {DISCHARGED}
#   DISCHARGED      → {} (terminal)
#
# Total valid: 1+2+1+1+1+0 = 6

EXPECTED_VALID_PATIENT: list[tuple[PatientState, PatientState]] = [
    (PatientState.AWAITING_BED, PatientState.BED_ASSIGNED),
    (PatientState.BED_ASSIGNED, PatientState.TRANSPORT_READY),
    (PatientState.BED_ASSIGNED, PatientState.AWAITING_BED),
    (PatientState.TRANSPORT_READY, PatientState.IN_TRANSIT),
    (PatientState.IN_TRANSIT, PatientState.ARRIVED),
    (PatientState.ARRIVED, PatientState.DISCHARGED),
]

_ALL_PATIENT_PAIRS = [
    (f, t) for f, t in product(PatientState, PatientState) if f != t
]

INVALID_PATIENT: list[tuple[PatientState, PatientState]] = [
    pair for pair in _ALL_PATIENT_PAIRS if pair not in EXPECTED_VALID_PATIENT
]


class TestPatientTransitions:
    """Exhaustive patient state-machine coverage."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        EXPECTED_VALID_PATIENT,
        ids=[f"{f.value}→{t.value}" for f, t in EXPECTED_VALID_PATIENT],
    )
    def test_valid_patient_transition_succeeds(self, from_state, to_state):
        validate_transition(from_state, to_state, VALID_PATIENT_TRANSITIONS)

    @pytest.mark.parametrize(
        "from_state,to_state",
        INVALID_PATIENT,
        ids=[f"{f.value}→{t.value}" for f, t in INVALID_PATIENT],
    )
    def test_invalid_patient_transition_raises(self, from_state, to_state):
        with pytest.raises(InvalidTransitionError):
            validate_transition(from_state, to_state, VALID_PATIENT_TRANSITIONS)

    def test_valid_transition_count(self):
        assert len(EXPECTED_VALID_PATIENT) == 6

    def test_invalid_transition_count(self):
        # 6 × 5 = 30 minus 6 valid = 24 invalid
        assert len(INVALID_PATIENT) == 24

    def test_discharged_is_terminal(self):
        """DISCHARGED has no outgoing transitions."""
        for target in PatientState:
            if target == PatientState.DISCHARGED:
                continue
            with pytest.raises(InvalidTransitionError):
                validate_transition(PatientState.DISCHARGED, target, VALID_PATIENT_TRANSITIONS)

    def test_awaiting_bed_is_entry_point(self):
        """AWAITING_BED can only go to BED_ASSIGNED."""
        for target in PatientState:
            if target == PatientState.AWAITING_BED:
                continue
            if target == PatientState.BED_ASSIGNED:
                validate_transition(PatientState.AWAITING_BED, target, VALID_PATIENT_TRANSITIONS)
            else:
                with pytest.raises(InvalidTransitionError):
                    validate_transition(PatientState.AWAITING_BED, target, VALID_PATIENT_TRANSITIONS)

    def test_bed_assigned_can_revert_to_awaiting(self):
        """BED_ASSIGNED → AWAITING_BED for reservation cancellation."""
        validate_transition(PatientState.BED_ASSIGNED, PatientState.AWAITING_BED, VALID_PATIENT_TRANSITIONS)


# ===================================================================
# TASK TRANSITIONS
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
    """Exhaustive task state-machine coverage."""

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
                validate_transition(TaskState.COMPLETED, target, VALID_TASK_TRANSITIONS)

    def test_cancelled_is_terminal(self):
        """CANCELLED has no outgoing transitions."""
        for target in TaskState:
            if target == TaskState.CANCELLED:
                continue
            with pytest.raises(InvalidTransitionError):
                validate_transition(TaskState.CANCELLED, target, VALID_TASK_TRANSITIONS)

    def test_escalated_can_resume_or_cancel(self):
        """ESCALATED → IN_PROGRESS (resume) and ESCALATED → CANCELLED."""
        validate_transition(TaskState.ESCALATED, TaskState.IN_PROGRESS, VALID_TASK_TRANSITIONS)
        validate_transition(TaskState.ESCALATED, TaskState.CANCELLED, VALID_TASK_TRANSITIONS)

    def test_accepted_cannot_cancel_directly(self):
        """ACCEPTED can only go to IN_PROGRESS (no direct cancel)."""
        with pytest.raises(InvalidTransitionError):
            validate_transition(TaskState.ACCEPTED, TaskState.CANCELLED, VALID_TASK_TRANSITIONS)
