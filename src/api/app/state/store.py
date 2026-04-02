"""In-memory state store with transition validation and seed data."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from ..models.entities import Bed, Patient, Reservation, Task, Transport
from ..models.enums import AdmissionSource, BedState, PatientState, TaskState
from ..models.transitions import (
    VALID_BED_TRANSITIONS,
    VALID_PATIENT_TRANSITIONS,
    VALID_TASK_TRANSITIONS,
    validate_transition,
)


# ── Hospital configuration (campuses, units, clinical rules) ────────

HOSPITAL_CONFIG: dict[str, Any] = {
    "campuses": {
        "main": {
            "id": "main",
            "name": "Main Campus",
            "has_dedicated_transporters": True,
        },
        "satellite": {
            "id": "satellite",
            "name": "Satellite Campus",
            "has_dedicated_transporters": False,
        },
    },
    "units": {
        "4-North": {
            "id": "4-North",
            "name": "4-North",
            "campus_id": "main",
            "specialty": "Med/Surg",
            "allowed_diagnoses": [
                "pneumonia", "fracture", "hip fracture",
                "post-op", "appendectomy", "appendicitis", "surgery",
                "general", "observation",
            ],
        },
        "5-South": {
            "id": "5-South",
            "name": "5-South",
            "campus_id": "main",
            "specialty": "Cardiac/Telemetry",
            "allowed_diagnoses": [
                "chest pain", "acs", "cardiac", "chf",
                "heart failure", "arrhythmia", "telemetry",
                "atrial fibrillation", "mi", "stemi", "nstemi",
            ],
        },
        "2-East": {
            "id": "2-East",
            "name": "2-East",
            "campus_id": "satellite",
            "specialty": "Med/Surg",
            "allowed_diagnoses": [
                "pneumonia", "fracture", "hip fracture",
                "post-op", "appendectomy", "appendicitis", "surgery",
                "general", "observation",
            ],
        },
    },
}


def get_unit_for_diagnosis(diagnosis: str) -> list[str]:
    """Return unit IDs whose allowed_diagnoses match the given diagnosis (keyword match)."""
    diagnosis_lower = diagnosis.lower()
    matching_units = []
    for unit_id, unit_cfg in HOSPITAL_CONFIG["units"].items():
        allowed = unit_cfg.get("allowed_diagnoses") or []
        for keyword in allowed:
            if keyword in diagnosis_lower:
                matching_units.append(unit_id)
                break
    return matching_units


def get_campus_for_unit(unit_id: str) -> dict | None:
    """Return the campus config dict for a given unit."""
    unit_cfg = HOSPITAL_CONFIG["units"].get(unit_id)
    if not unit_cfg:
        return None
    return HOSPITAL_CONFIG["campuses"].get(unit_cfg["campus_id"])


class StateStore:
    """Authoritative in-memory state for beds, patients, tasks, transports, and reservations.

    All mutations acquire ``_lock`` and run state-machine validation via
    ``transitions.validate_transition`` before changing entity state.
    """

    def __init__(self) -> None:
        self.beds: dict[str, Bed] = {}
        self.patients: dict[str, Patient] = {}
        self.tasks: dict[str, Task] = {}
        self.transports: dict[str, Transport] = {}
        self.reservations: dict[str, Reservation] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    # ── Getters ─────────────────────────────────────────────────────

    def get_bed(self, bed_id: str) -> Optional[Bed]:
        return self.beds.get(bed_id)

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        return self.patients.get(patient_id)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def get_transport(self, transport_id: str) -> Optional[Transport]:
        return self.transports.get(transport_id)

    def get_reservation(self, reservation_id: str) -> Optional[Reservation]:
        return self.reservations.get(reservation_id)

    def get_beds(
        self, filter_fn: Optional[Callable[[Bed], bool]] = None
    ) -> list[Bed]:
        beds = list(self.beds.values())
        if filter_fn:
            beds = [b for b in beds if filter_fn(b)]
        return beds

    def get_patients(
        self, filter_fn: Optional[Callable[[Patient], bool]] = None
    ) -> list[Patient]:
        patients = list(self.patients.values())
        if filter_fn:
            patients = [p for p in patients if filter_fn(p)]
        return patients

    def get_tasks(
        self, filter_fn: Optional[Callable[[Task], bool]] = None
    ) -> list[Task]:
        tasks = list(self.tasks.values())
        if filter_fn:
            tasks = [t for t in tasks if filter_fn(t)]
        return tasks

    def get_transports(
        self, filter_fn: Optional[Callable[[Transport], bool]] = None
    ) -> list[Transport]:
        transports = list(self.transports.values())
        if filter_fn:
            transports = [t for t in transports if filter_fn(t)]
        return transports

    def get_active_reservations(self) -> list[Reservation]:
        return [r for r in self.reservations.values() if r.is_active]

    # ── State-transition helpers ────────────────────────────────────

    async def transition_bed(self, bed_id: str, new_state: BedState) -> Bed:
        async with self._lock:
            bed = self.beds.get(bed_id)
            if bed is None:
                raise KeyError(f"Bed {bed_id} not found")
            validate_transition(bed.state, new_state, VALID_BED_TRANSITIONS)
            bed.state = new_state
            bed.last_state_change = datetime.now(timezone.utc)
            return bed

    async def transition_patient(
        self, patient_id: str, new_state: PatientState
    ) -> Patient:
        async with self._lock:
            patient = self.patients.get(patient_id)
            if patient is None:
                raise KeyError(f"Patient {patient_id} not found")
            validate_transition(
                patient.state, new_state, VALID_PATIENT_TRANSITIONS
            )
            patient.state = new_state
            return patient

    async def transition_task(
        self, task_id: str, new_state: TaskState
    ) -> Task:
        async with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                raise KeyError(f"Task {task_id} not found")
            validate_transition(task.state, new_state, VALID_TASK_TRANSITIONS)
            task.state = new_state
            return task

    async def transition_transport(
        self, transport_id: str, new_state: TaskState
    ) -> Transport:
        async with self._lock:
            transport = self.transports.get(transport_id)
            if transport is None:
                raise KeyError(f"Transport {transport_id} not found")
            validate_transition(
                transport.state, new_state, VALID_TASK_TRANSITIONS
            )
            transport.state = new_state
            return transport

    # ── Seed data ───────────────────────────────────────────────────

    def seed_initial_state(self) -> None:
        """Populate a default hospital bed layout.

        Creates 12 beds across 2 units (6 beds each) with a realistic
        mix of states for demo purposes.
        """
        now = datetime.now(timezone.utc)

        # Predefined state distribution for a realistic starting board
        bed_configs: list[dict] = [
            # Unit A — 6 beds in 3 rooms (A/B per room)
            {"unit": "4-North", "room": "401", "letter": "A", "state": BedState.OCCUPIED, "patient_id": "P-EXIST-01"},
            {"unit": "4-North", "room": "401", "letter": "B", "state": BedState.READY},
            {"unit": "4-North", "room": "402", "letter": "A", "state": BedState.OCCUPIED, "patient_id": "P-EXIST-02"},
            {"unit": "4-North", "room": "402", "letter": "B", "state": BedState.DIRTY},
            {"unit": "4-North", "room": "403", "letter": "A", "state": BedState.CLEANING},
            {"unit": "4-North", "room": "403", "letter": "B", "state": BedState.BLOCKED},
            # Unit B — 6 beds in 3 rooms
            {"unit": "5-South", "room": "501", "letter": "A", "state": BedState.OCCUPIED, "patient_id": "P-EXIST-03"},
            {"unit": "5-South", "room": "501", "letter": "B", "state": BedState.READY},
            {"unit": "5-South", "room": "502", "letter": "A", "state": BedState.DIRTY},
            {"unit": "5-South", "room": "502", "letter": "B", "state": BedState.READY},
            {"unit": "5-South", "room": "503", "letter": "A", "state": BedState.OCCUPIED, "patient_id": "P-EXIST-04"},
            {"unit": "5-South", "room": "503", "letter": "B", "state": BedState.CLEANING},
            # Satellite Campus — 4 beds in 2 rooms (no dedicated transporters)
            {"unit": "2-East", "room": "201", "letter": "A", "state": BedState.OCCUPIED, "patient_id": "P-EXIST-05"},
            {"unit": "2-East", "room": "201", "letter": "B", "state": BedState.READY},
            {"unit": "2-East", "room": "202", "letter": "A", "state": BedState.DIRTY},
            {"unit": "2-East", "room": "202", "letter": "B", "state": BedState.READY},
        ]

        for i, cfg in enumerate(bed_configs, start=1):
            bed_id = f"BED-{cfg['room']}{cfg['letter']}"
            self.beds[bed_id] = Bed(
                id=bed_id,
                unit=cfg["unit"],
                room_number=cfg["room"],
                bed_letter=cfg["letter"],
                state=cfg["state"],
                patient_id=cfg.get("patient_id"),
                last_state_change=now - timedelta(minutes=30 * i),
            )

        # Seed existing patients (those occupying beds)
        existing_patients = [
            {"id": "P-EXIST-01", "name": "Maria Santos", "mrn": "MRN-10001", "location": "4-North 401A", "bed": "BED-401A", "diagnosis": "Pneumonia", "acuity": 3},
            {"id": "P-EXIST-02", "name": "James Chen", "mrn": "MRN-10002", "location": "4-North 402A", "bed": "BED-402A", "diagnosis": "Hip fracture", "acuity": 2},
            {"id": "P-EXIST-03", "name": "Aisha Williams", "mrn": "MRN-10003", "location": "5-South 501A", "bed": "BED-501A", "diagnosis": "CHF exacerbation", "acuity": 4},
            {"id": "P-EXIST-04", "name": "Robert Kim", "mrn": "MRN-10004", "location": "5-South 503A", "bed": "BED-503A", "diagnosis": "Post-op appendectomy", "acuity": 2},
            {"id": "P-EXIST-05", "name": "Linda Torres", "mrn": "MRN-10005", "location": "2-East 201A", "bed": "BED-201A", "diagnosis": "Pneumonia", "acuity": 3},
        ]

        for pcfg in existing_patients:
            self.patients[pcfg["id"]] = Patient(
                id=pcfg["id"],
                name=pcfg["name"],
                mrn=pcfg["mrn"],
                state=PatientState.ARRIVED,
                current_location=pcfg["location"],
                assigned_bed_id=pcfg["bed"],
                diagnosis=pcfg["diagnosis"],
                acuity_level=pcfg["acuity"],
                requested_at=now - timedelta(hours=6),
            )

    # ── Snapshot ────────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """Return all state as a serializable dict for ``GET /api/state``."""
        return {
            "beds": {k: v.model_dump(mode="json") for k, v in self.beds.items()},
            "patients": {k: v.model_dump(mode="json") for k, v in self.patients.items()},
            "tasks": {k: v.model_dump(mode="json") for k, v in self.tasks.items()},
            "transports": {k: v.model_dump(mode="json") for k, v in self.transports.items()},
            "reservations": {k: v.model_dump(mode="json") for k, v in self.reservations.items()},
            "hospital_config": HOSPITAL_CONFIG,
        }

    # ── Lifecycle ───────────────────────────────────────────────────

    def clear(self) -> None:
        """Wipe all state for a scenario reset."""
        self.beds.clear()
        self.patients.clear()
        self.tasks.clear()
        self.transports.clear()
        self.reservations.clear()
