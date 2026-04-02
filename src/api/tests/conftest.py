"""
Shared test fixtures for the bed-management API test suite.

These fixtures depend on domain models from app.models and stores from
app.events.event_store / app.state.store / app.messages.message_store.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.models.enums import BedState, PatientState, TaskState, TaskType
from app.models.entities import Bed, Patient, Task, Transport, Reservation
from app.events.event_store import EventStore
from app.messages.message_store import MessageStore
from app.metrics.metrics_store import MetricsStore
from app.state.store import StateStore


# ---------------------------------------------------------------------------
# Store fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_store() -> EventStore:
    """Fresh event store — cleared after each test."""
    store = EventStore()
    yield store
    store.clear()


@pytest.fixture
def state_store() -> StateStore:
    """Fresh state store — cleared after each test."""
    store = StateStore()
    yield store
    store.clear()


@pytest.fixture
def message_store() -> MessageStore:
    """Fresh message store — cleared after each test."""
    store = MessageStore()
    yield store
    store.clear()


@pytest.fixture
def metrics_store() -> MetricsStore:
    """Fresh metrics store — cleared after each test."""
    store = MetricsStore()
    yield store
    store.clear()


@pytest.fixture
def seeded_state_store(state_store: StateStore) -> StateStore:
    """State store pre-seeded with the standard hospital bed layout."""
    state_store.seed_initial_state()
    return state_store


# ---------------------------------------------------------------------------
# Sample entity fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_beds() -> list[Bed]:
    """Six beds covering every BedState value."""
    return [
        Bed(id="bed-001", unit="ED", room_number="101", bed_letter="A", state=BedState.READY),
        Bed(id="bed-002", unit="ED", room_number="101", bed_letter="B", state=BedState.OCCUPIED),
        Bed(id="bed-003", unit="MedSurg", room_number="201", bed_letter="A", state=BedState.DIRTY),
        Bed(id="bed-004", unit="MedSurg", room_number="201", bed_letter="B", state=BedState.CLEANING),
        Bed(id="bed-005", unit="ICU", room_number="301", bed_letter="A", state=BedState.RESERVED),
        Bed(id="bed-006", unit="ICU", room_number="301", bed_letter="B", state=BedState.BLOCKED),
    ]


@pytest.fixture
def sample_patients() -> list[Patient]:
    """Patients at various stages of the admission workflow."""
    return [
        Patient(id="pat-001", name="Alice Johnson", mrn="MRN-001", current_location="ED Bay 1", state=PatientState.AWAITING_BED),
        Patient(
            id="pat-002",
            name="Bob Smith",
            mrn="MRN-002",
            current_location="ED Bay 2",
            state=PatientState.BED_ASSIGNED,
            assigned_bed_id="bed-005",
        ),
        Patient(id="pat-003", name="Carol Davis", mrn="MRN-003", current_location="Hallway B", state=PatientState.IN_TRANSIT),
        Patient(
            id="pat-004",
            name="Dan Wilson",
            mrn="MRN-004",
            current_location="MedSurg 201A",
            state=PatientState.ARRIVED,
            assigned_bed_id="bed-002",
        ),
    ]


@pytest.fixture
def sample_tasks() -> list[Task]:
    """Tasks in various completion states."""
    return [
        Task(
            id="task-001",
            type=TaskType.EVS_CLEANING,
            subject_id="bed-003",
            state=TaskState.CREATED,
        ),
        Task(
            id="task-002",
            type=TaskType.EVS_CLEANING,
            subject_id="bed-004",
            state=TaskState.IN_PROGRESS,
        ),
        Task(
            id="task-003",
            type=TaskType.TRANSPORT,
            subject_id="pat-004",
            state=TaskState.COMPLETED,
        ),
    ]


# ---------------------------------------------------------------------------
# FastAPI async test client
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_client():
    """Async HTTP client wired to the FastAPI app (no real server needed).

    Resets the singleton stores before each test so endpoint tests get clean state.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.state import store as singleton_state_store
    from app.events import event_store as singleton_event_store
    from app.messages import message_store as singleton_message_store
    from app.metrics import metrics_store as singleton_metrics_store

    singleton_state_store.clear()
    singleton_event_store.clear()
    singleton_message_store.clear()
    singleton_metrics_store.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    singleton_state_store.clear()
    singleton_event_store.clear()
    singleton_message_store.clear()
    singleton_metrics_store.clear()
