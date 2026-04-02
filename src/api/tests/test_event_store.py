"""
Event store tests — publish, retrieve, filter, clear, subscribe.

The event store is the append-only audit trail (ADR-002). Every state
mutation emits an event with a monotonic sequence number. The actual API:
  - publish(event_type, entity_id, payload, state_diff) → Event  (async)
  - get_events(since_sequence) → list[Event]                     (sync)
  - subscribe() → asyncio.Queue[Event]                           (async)
  - clear()                                                       (sync)
"""

import asyncio
import pytest

from app.events.event_store import EventStore


class TestEventPublish:
    """Publishing events to the store."""

    async def test_publish_returns_event_with_sequence(self, event_store: EventStore):
        event = await event_store.publish(
            event_type="BedReserved",
            entity_id="bed-001",
            payload={"patient_id": "pat-001", "bed_id": "bed-001"},
        )
        assert event.sequence >= 1
        assert event.event_type == "BedReserved"
        assert event.entity_id == "bed-001"

    async def test_publish_event_has_timestamp(self, event_store: EventStore):
        event = await event_store.publish(
            event_type="BedReserved",
            entity_id="bed-001",
            payload={},
        )
        assert event.timestamp is not None

    async def test_publish_event_has_unique_id(self, event_store: EventStore):
        e1 = await event_store.publish("BedReserved", "bed-001", {})
        e2 = await event_store.publish("BedReleased", "bed-001", {})
        assert e1.id != e2.id

    async def test_sequence_is_monotonically_increasing(self, event_store: EventStore):
        events = []
        for i in range(10):
            e = await event_store.publish(
                event_type=f"Event{i}",
                entity_id=f"entity-{i}",
                payload={"index": i},
            )
            events.append(e)

        sequences = [e.sequence for e in events]
        assert sequences == sorted(sequences), "Sequences must be monotonically increasing"
        assert len(set(sequences)) == 10, "All sequences must be unique"

    async def test_payload_preserved(self, event_store: EventStore):
        payload = {
            "patient_id": "pat-001",
            "bed_id": "bed-001",
            "reason": "high acuity match",
        }
        event = await event_store.publish("BedReserved", "bed-001", payload)
        assert event.payload == payload

    async def test_publish_with_state_diff(self, event_store: EventStore):
        event = await event_store.publish(
            event_type="BedStateChanged",
            entity_id="bed-001",
            payload={},
            state_diff={"from_state": "DIRTY", "to_state": "CLEANING"},
        )
        assert event.state_diff is not None
        assert event.state_diff.from_state == "DIRTY"
        assert event.state_diff.to_state == "CLEANING"

    async def test_publish_without_state_diff(self, event_store: EventStore):
        event = await event_store.publish("BedReserved", "bed-001", {})
        assert event.state_diff is None


class TestEventRetrieval:
    """Retrieving events from the store (sync get_events)."""

    async def test_get_events_returns_all_events_in_order(self, event_store: EventStore):
        for i in range(5):
            await event_store.publish(f"Event{i}", f"entity-{i}", {"i": i})

        events = event_store.get_events()
        assert len(events) == 5
        for i in range(1, len(events)):
            assert events[i].sequence > events[i - 1].sequence

    async def test_get_events_empty_store_returns_empty_list(self, event_store: EventStore):
        events = event_store.get_events()
        assert events == []

    async def test_get_events_since_sequence_filters_correctly(self, event_store: EventStore):
        published = []
        for i in range(10):
            e = await event_store.publish(f"Event{i}", f"entity-{i}", {})
            published.append(e)

        # Get events after the 5th event
        cutoff = published[4].sequence
        filtered = event_store.get_events(since_sequence=cutoff)

        # Should return events 5-9 (those AFTER the cutoff)
        assert len(filtered) == 5
        for e in filtered:
            assert e.sequence > cutoff

    async def test_get_events_since_future_sequence_returns_empty(self, event_store: EventStore):
        await event_store.publish("Event0", "entity-0", {})
        filtered = event_store.get_events(since_sequence=999999)
        assert filtered == []

    async def test_get_events_since_zero_returns_all(self, event_store: EventStore):
        for i in range(3):
            await event_store.publish(f"Event{i}", f"entity-{i}", {})
        all_events = event_store.get_events(since_sequence=0)
        assert len(all_events) == 3


class TestEventClear:
    """Clearing the event store."""

    async def test_clear_removes_all_events(self, event_store: EventStore):
        for i in range(5):
            await event_store.publish(f"Event{i}", f"entity-{i}", {})

        event_store.clear()
        events = event_store.get_events()
        assert events == []

    async def test_clear_resets_sequence(self, event_store: EventStore):
        for i in range(5):
            await event_store.publish(f"Event{i}", f"entity-{i}", {})

        event_store.clear()

        # Next event after clear should start from sequence 1
        e = await event_store.publish("AfterClear", "entity-new", {})
        assert e.sequence == 1


class TestEventSubscription:
    """Subscriber receives new events via asyncio.Queue."""

    async def test_subscriber_receives_new_events(self, event_store: EventStore):
        queue = await event_store.subscribe()

        await event_store.publish("BedReserved", "bed-001", {"test": True})

        event = queue.get_nowait()
        assert event.event_type == "BedReserved"

    async def test_multiple_subscribers_each_get_events(self, event_store: EventStore):
        queue_a = await event_store.subscribe()
        queue_b = await event_store.subscribe()

        await event_store.publish("BedReserved", "bed-001", {})

        event_a = queue_a.get_nowait()
        event_b = queue_b.get_nowait()
        assert event_a.event_type == "BedReserved"
        assert event_b.event_type == "BedReserved"

    async def test_subscriber_receives_multiple_events(self, event_store: EventStore):
        queue = await event_store.subscribe()

        for i in range(3):
            await event_store.publish(f"Event{i}", f"entity-{i}", {})

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        assert len(events) == 3
        types = [e.event_type for e in events]
        assert types == ["Event0", "Event1", "Event2"]

    async def test_unsubscribe_stops_receiving(self, event_store: EventStore):
        queue = await event_store.subscribe()
        event_store.unsubscribe(queue)

        await event_store.publish("BedReserved", "bed-001", {})

        assert queue.empty()
