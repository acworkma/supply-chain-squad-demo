"""State endpoint — returns the full current state snapshot."""

from fastapi import APIRouter

from app.state import store
from app.state.store import HOSPITAL_CONFIG

router = APIRouter(tags=["state"])


@router.get("/state")
async def get_state():
    """Return the full state snapshot (beds, patients, tasks, transports, reservations, hospital_config)."""
    async with store._lock:
        return {
            "beds": {k: v.model_dump(mode="json") for k, v in store.beds.items()},
            "patients": {k: v.model_dump(mode="json") for k, v in store.patients.items()},
            "tasks": {k: v.model_dump(mode="json") for k, v in store.tasks.items()},
            "transports": {k: v.model_dump(mode="json") for k, v in store.transports.items()},
            "reservations": {k: v.model_dump(mode="json") for k, v in store.reservations.items()},
            "hospital_config": HOSPITAL_CONFIG,
        }
