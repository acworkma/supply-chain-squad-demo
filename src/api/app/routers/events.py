"""Event endpoints — list and stream events."""

import asyncio

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from app.events import event_store

router = APIRouter(tags=["events"])


@router.get("/events")
async def get_events(since: int = Query(0, description="Return events with sequence > this value")):
    """Return events from the append-only store, optionally filtered by sequence."""
    events = event_store.get_events(since_sequence=since)
    return [e.model_dump(mode="json") for e in events]


@router.get("/events/stream")
async def stream_events():
    """SSE stream of events as they occur."""
    queue = await event_store.subscribe()

    async def event_generator():
        try:
            while True:
                event = await queue.get()
                yield {"data": event.model_dump_json()}
        finally:
            event_store.unsubscribe(queue)

    return EventSourceResponse(event_generator())
