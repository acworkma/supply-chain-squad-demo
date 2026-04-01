"""Append-only, in-memory event store with SSE subscriber support."""

import asyncio
import uuid
from datetime import datetime, timezone

from ..models.events import Event, StateDiff


class EventStore:
    """Append-only event log with monotonic sequence numbering.

    Events are immutable once appended. Subscribers (asyncio.Queue instances)
    are notified on every publish for SSE streaming.
    """

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._sequence_counter: int = 0
        self._lock: asyncio.Lock = asyncio.Lock()
        self._subscribers: list[asyncio.Queue[Event]] = []

    # ── Publishing ──────────────────────────────────────────────────

    async def publish(
        self,
        event_type: str,
        entity_id: str,
        payload: dict | None = None,
        state_diff: dict | None = None,
    ) -> Event:
        """Create, append, and broadcast a new event.

        Returns the fully-populated ``Event`` with its assigned sequence number.
        """
        async with self._lock:
            self._sequence_counter += 1
            diff = (
                StateDiff(
                    from_state=state_diff["from_state"],
                    to_state=state_diff["to_state"],
                )
                if state_diff
                else None
            )
            event = Event(
                id=str(uuid.uuid4()),
                sequence=self._sequence_counter,
                timestamp=datetime.now(timezone.utc),
                event_type=event_type,
                entity_id=entity_id,
                payload=payload or {},
                state_diff=diff,
            )
            self._events.append(event)

        # Notify subscribers outside the lock to avoid blocking
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow consumer — drop event rather than block

        return event

    # ── Querying ────────────────────────────────────────────────────

    def get_events(self, since_sequence: int = 0) -> list[Event]:
        """Return events with sequence > *since_sequence*."""
        return [e for e in self._events if e.sequence > since_sequence]

    # ── SSE Subscription ────────────────────────────────────────────

    async def subscribe(self) -> asyncio.Queue[Event]:
        """Create a new subscriber queue for SSE streaming."""
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        """Remove a subscriber queue."""
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    # ── Lifecycle ───────────────────────────────────────────────────

    def clear(self) -> None:
        """Reset the store for scenario replay."""
        self._events.clear()
        self._sequence_counter = 0
        # Don't clear subscribers — live SSE connections should see the reset
