"""Shared asyncio.Event used to wake the human-approval polling loop.

Set by:
  - POST /api/approval/{po_id}  (human clicked approve/reject)
  - POST /api/scenario/seed     (user hit Reset)
  - POST /api/scenario/*        (new scenario clearing old state)

Awaited by:
  - orchestrator._wait_for_human_approval()
"""

import asyncio

# The event is re-created each time a scenario starts waiting.
# We store it in a mutable container so all modules share the same reference.
_approval_event: asyncio.Event | None = None


def create_event() -> asyncio.Event:
    """Create a fresh Event for a new approval wait cycle."""
    global _approval_event
    _approval_event = asyncio.Event()
    return _approval_event


def signal() -> None:
    """Wake the polling loop (if one is waiting)."""
    if _approval_event is not None:
        _approval_event.set()
