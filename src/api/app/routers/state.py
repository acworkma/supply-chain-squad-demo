"""State endpoint — returns the full current state snapshot."""

from fastapi import APIRouter

from app.state import store

router = APIRouter(tags=["state"])


@router.get("/state")
async def get_state():
    """Return the full state snapshot (closets, items, vendors, catalog, scans, POs, shipments)."""
    return store.get_snapshot()
