"""
Entity model tests — creating entities, enum completeness, serialization, defaults.

These tests serve as a specification for WI-002 domain model implementation.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone

from app.models.enums import AdmissionSource, BedState, PatientState, TaskState, TaskType, TransportPriority, IntentTag
from app.models.entities import Bed, Patient, Task, Transport, Reservation, AgentMessage


# ===================================================================
# Enum completeness — every expected state exists
# ===================================================================

class TestBedStateEnum:
    """BedState must contain exactly the 6 states from the spec."""

    EXPECTED_VALUES = {"OCCUPIED", "RESERVED", "DIRTY", "CLEANING", "READY", "BLOCKED"}

    def test_all_expected_values_exist(self):
        actual = {s.value for s in BedState}
        assert self.EXPECTED_VALUES == actual, (
            f"BedState mismatch.\n"
            f"  Missing: {self.EXPECTED_VALUES - actual}\n"
            f"  Extra:   {actual - self.EXPECTED_VALUES}"
        )

    def test_enum_count(self):
        assert len(BedState) == 6

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert BedState(value).value == value


class TestPatientStateEnum:
    """PatientState must contain exactly the 6 states from the spec."""

    EXPECTED_VALUES = {
        "AWAITING_BED", "BED_ASSIGNED", "TRANSPORT_READY",
        "IN_TRANSIT", "ARRIVED", "DISCHARGED",
    }

    def test_all_expected_values_exist(self):
        actual = {s.value for s in PatientState}
        assert self.EXPECTED_VALUES == actual, (
            f"PatientState mismatch.\n"
            f"  Missing: {self.EXPECTED_VALUES - actual}\n"
            f"  Extra:   {actual - self.EXPECTED_VALUES}"
        )

    def test_enum_count(self):
        assert len(PatientState) == 6

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert PatientState(value).value == value


class TestTaskStateEnum:
    """TaskState must contain exactly the 6 states from the spec."""

    EXPECTED_VALUES = {
        "CREATED", "ACCEPTED", "IN_PROGRESS",
        "COMPLETED", "ESCALATED", "CANCELLED",
    }

    def test_all_expected_values_exist(self):
        actual = {s.value for s in TaskState}
        assert self.EXPECTED_VALUES == actual, (
            f"TaskState mismatch.\n"
            f"  Missing: {self.EXPECTED_VALUES - actual}\n"
            f"  Extra:   {actual - self.EXPECTED_VALUES}"
        )

    def test_enum_count(self):
        assert len(TaskState) == 6

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert TaskState(value).value == value


class TestTaskTypeEnum:
    """TaskType covers the domain task categories."""

    EXPECTED_VALUES = {"EVS_CLEANING", "TRANSPORT", "BED_PREP", "OTHER"}

    def test_all_expected_values_exist(self):
        actual = {t.value for t in TaskType}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(TaskType) == 4


class TestTransportPriorityEnum:

    EXPECTED_VALUES = {"STAT", "URGENT", "ROUTINE"}

    def test_all_expected_values_exist(self):
        actual = {p.value for p in TransportPriority}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(TransportPriority) == 3


class TestAdmissionSourceEnum:
    EXPECTED_VALUES = {"ER", "OR", "DIRECT_ADMIT", "TRANSFER"}

    def test_all_expected_values_exist(self):
        actual = {s.value for s in AdmissionSource}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(AdmissionSource) == 4


class TestIntentTagEnum:

    EXPECTED_VALUES = {"PROPOSE", "VALIDATE", "EXECUTE", "ESCALATE"}

    def test_all_expected_values_exist(self):
        actual = {t.value for t in IntentTag}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(IntentTag) == 4


# ===================================================================
# Entity creation — constructing each type with required fields
# ===================================================================

class TestBedCreation:

    def test_create_bed_with_required_fields(self):
        bed = Bed(id="bed-100", unit="ED", room_number="100", bed_letter="A")
        assert bed.id == "bed-100"
        assert bed.unit == "ED"
        assert bed.room_number == "100"
        assert bed.bed_letter == "A"

    def test_bed_default_state_is_ready(self):
        bed = Bed(id="bed-100", unit="ED", room_number="100", bed_letter="A")
        assert bed.state == BedState.READY

    def test_create_bed_with_explicit_state(self):
        bed = Bed(id="bed-100", unit="ED", room_number="100", bed_letter="A", state=BedState.OCCUPIED)
        assert bed.state == BedState.OCCUPIED

    def test_bed_optional_patient_id_defaults_none(self):
        bed = Bed(id="bed-100", unit="ED", room_number="100", bed_letter="A")
        assert bed.patient_id is None

    def test_bed_optional_reserved_for_defaults_none(self):
        bed = Bed(id="bed-100", unit="ED", room_number="100", bed_letter="A")
        assert bed.reserved_for_patient_id is None

    def test_bed_has_last_state_change_timestamp(self):
        bed = Bed(id="bed-100", unit="ED", room_number="100", bed_letter="A")
        assert isinstance(bed.last_state_change, datetime)


class TestPatientCreation:

    def test_create_patient_with_required_fields(self):
        patient = Patient(id="pat-100", name="Test Patient", mrn="MRN-100", current_location="ED Bay 1")
        assert patient.id == "pat-100"
        assert patient.name == "Test Patient"
        assert patient.mrn == "MRN-100"
        assert patient.current_location == "ED Bay 1"

    def test_patient_default_state_is_awaiting_bed(self):
        patient = Patient(id="pat-100", name="Test Patient", mrn="MRN-100", current_location="ED Bay 1")
        assert patient.state == PatientState.AWAITING_BED

    def test_create_patient_with_explicit_state(self):
        patient = Patient(
            id="pat-100", name="Test Patient", mrn="MRN-100",
            current_location="ED Bay 1", state=PatientState.IN_TRANSIT,
        )
        assert patient.state == PatientState.IN_TRANSIT

    def test_patient_optional_bed_id_defaults_none(self):
        patient = Patient(id="pat-100", name="Test Patient", mrn="MRN-100", current_location="ED Bay 1")
        assert patient.assigned_bed_id is None

    def test_patient_default_acuity_is_3(self):
        patient = Patient(id="pat-100", name="Test Patient", mrn="MRN-100", current_location="ED Bay 1")
        assert patient.acuity_level == 3

    def test_patient_acuity_range_validation(self):
        """Acuity must be 1-5."""
        with pytest.raises(Exception):
            Patient(id="pat-100", name="Test", mrn="MRN-100", current_location="ED", acuity_level=0)
        with pytest.raises(Exception):
            Patient(id="pat-100", name="Test", mrn="MRN-100", current_location="ED", acuity_level=6)

    def test_patient_has_requested_at_timestamp(self):
        patient = Patient(id="pat-100", name="Test Patient", mrn="MRN-100", current_location="ED Bay 1")
        assert isinstance(patient.requested_at, datetime)


class TestTaskCreation:

    def test_create_task_with_required_fields(self):
        task = Task(id="task-100", type=TaskType.EVS_CLEANING, subject_id="bed-003")
        assert task.id == "task-100"
        assert task.type == TaskType.EVS_CLEANING
        assert task.subject_id == "bed-003"

    def test_task_default_state_is_created(self):
        task = Task(id="task-100", type=TaskType.EVS_CLEANING, subject_id="bed-003")
        assert task.state == TaskState.CREATED

    def test_create_task_with_explicit_state(self):
        task = Task(id="task-100", type=TaskType.EVS_CLEANING, subject_id="bed-003", state=TaskState.IN_PROGRESS)
        assert task.state == TaskState.IN_PROGRESS

    def test_task_default_priority_is_routine(self):
        task = Task(id="task-100", type=TaskType.TRANSPORT, subject_id="pat-001")
        assert task.priority == TransportPriority.ROUTINE

    def test_task_optional_assigned_to_defaults_none(self):
        task = Task(id="task-100", type=TaskType.EVS_CLEANING, subject_id="bed-003")
        assert task.assigned_to is None

    def test_task_has_created_at_timestamp(self):
        task = Task(id="task-100", type=TaskType.EVS_CLEANING, subject_id="bed-003")
        assert isinstance(task.created_at, datetime)


class TestTransportCreation:

    def test_create_transport_with_required_fields(self):
        transport = Transport(
            id="trans-100",
            patient_id="pat-001",
            from_location="ED Bay 3",
            to_location="MedSurg 201A",
        )
        assert transport.id == "trans-100"
        assert transport.patient_id == "pat-001"
        assert transport.from_location == "ED Bay 3"
        assert transport.to_location == "MedSurg 201A"

    def test_transport_default_state_is_created(self):
        transport = Transport(id="trans-100", patient_id="pat-001", from_location="ED", to_location="Room")
        assert transport.state == TaskState.CREATED

    def test_transport_default_priority_is_routine(self):
        transport = Transport(id="trans-100", patient_id="pat-001", from_location="ED", to_location="Room")
        assert transport.priority == TransportPriority.ROUTINE


class TestReservationCreation:

    def test_create_reservation_with_required_fields(self):
        hold = datetime.now(timezone.utc) + timedelta(hours=1)
        reservation = Reservation(
            id="res-100",
            bed_id="bed-001",
            patient_id="pat-001",
            hold_until=hold,
        )
        assert reservation.id == "res-100"
        assert reservation.bed_id == "bed-001"
        assert reservation.patient_id == "pat-001"
        assert reservation.hold_until == hold

    def test_reservation_default_is_active(self):
        hold = datetime.now(timezone.utc) + timedelta(hours=1)
        reservation = Reservation(id="res-100", bed_id="bed-001", patient_id="pat-001", hold_until=hold)
        assert reservation.is_active is True

    def test_reservation_has_created_at(self):
        hold = datetime.now(timezone.utc) + timedelta(hours=1)
        reservation = Reservation(id="res-100", bed_id="bed-001", patient_id="pat-001", hold_until=hold)
        assert isinstance(reservation.created_at, datetime)


class TestAgentMessageCreation:

    def test_create_agent_message(self):
        msg = AgentMessage(
            id="msg-001",
            agent_name="BedCoordinator",
            agent_role="coordinator",
            content="Analyzing bed options.",
            intent_tag=IntentTag.PROPOSE,
        )
        assert msg.id == "msg-001"
        assert msg.agent_name == "BedCoordinator"
        assert msg.intent_tag == IntentTag.PROPOSE

    def test_agent_message_default_related_events_empty(self):
        msg = AgentMessage(
            id="msg-001",
            agent_name="BedCoordinator",
            agent_role="coordinator",
            content="Test",
            intent_tag=IntentTag.EXECUTE,
        )
        assert msg.related_event_ids == []


# ===================================================================
# Serialization / deserialization — Pydantic model_dump / model_validate
# ===================================================================

class TestBedSerialization:

    def test_bed_round_trips_through_dict(self):
        bed = Bed(id="bed-100", unit="ED", room_number="100", bed_letter="A", state=BedState.DIRTY)
        data = bed.model_dump()
        restored = Bed.model_validate(data)
        assert restored == bed

    def test_bed_round_trips_through_json(self):
        bed = Bed(id="bed-100", unit="ED", room_number="100", bed_letter="A", state=BedState.RESERVED)
        json_str = bed.model_dump_json()
        restored = Bed.model_validate_json(json_str)
        assert restored == bed

    def test_bed_dict_has_expected_keys(self):
        bed = Bed(id="bed-100", unit="ED", room_number="100", bed_letter="A")
        data = bed.model_dump()
        assert "id" in data
        assert "unit" in data
        assert "room_number" in data
        assert "bed_letter" in data
        assert "state" in data


class TestPatientSerialization:

    def test_patient_round_trips_through_dict(self):
        patient = Patient(
            id="pat-100", name="Test Patient", mrn="MRN-100",
            current_location="ED Bay 1",
            state=PatientState.BED_ASSIGNED,
            assigned_bed_id="bed-005",
        )
        data = patient.model_dump()
        restored = Patient.model_validate(data)
        assert restored == patient

    def test_patient_round_trips_through_json(self):
        patient = Patient(id="pat-100", name="Test Patient", mrn="MRN-100", current_location="ED Bay 1")
        json_str = patient.model_dump_json()
        restored = Patient.model_validate_json(json_str)
        assert restored == patient


class TestTaskSerialization:

    def test_task_round_trips_through_dict(self):
        task = Task(
            id="task-100",
            type=TaskType.EVS_CLEANING,
            subject_id="bed-004",
            state=TaskState.IN_PROGRESS,
        )
        data = task.model_dump()
        restored = Task.model_validate(data)
        assert restored == task

    def test_task_round_trips_through_json(self):
        task = Task(id="task-100", type=TaskType.TRANSPORT, subject_id="pat-001")
        json_str = task.model_dump_json()
        restored = Task.model_validate_json(json_str)
        assert restored == task
