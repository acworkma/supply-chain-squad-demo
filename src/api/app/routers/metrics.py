"""Metrics endpoints — scenario run metrics."""

from fastapi import APIRouter, Query

from app.metrics import metrics_store

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_latest_metrics():
    """Return the latest scenario run metrics, or a message if none recorded."""
    latest = metrics_store.get_latest()
    if latest is None:
        return {"message": "No scenario runs recorded yet"}
    return latest


@router.get("/metrics/history")
async def get_metrics_history(
    limit: int = Query(10, ge=1, le=100, description="Number of recent runs to return"),
):
    """Return the last N scenario run metrics, most recent first."""
    history = metrics_store.get_history(limit=limit)
    if not history:
        return {"message": "No scenario runs recorded yet"}
    return history
