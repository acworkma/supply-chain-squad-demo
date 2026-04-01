"""In-memory message store with SSE subscriber support for agent conversation transcripts."""

import asyncio
import uuid
from datetime import datetime, timezone

from ..models.entities import AgentMessage
from ..models.enums import IntentTag


class MessageStore:
    """Append-only store for agent-to-agent messages.

    Mirrors ``EventStore`` pattern: publish appends and broadcasts to SSE subscribers.
    """

    def __init__(self) -> None:
        self._messages: list[AgentMessage] = []
        self._lock: asyncio.Lock = asyncio.Lock()
        self._subscribers: list[asyncio.Queue[AgentMessage]] = []

    # ── Publishing ──────────────────────────────────────────────────

    async def publish(
        self,
        agent_name: str,
        agent_role: str,
        content: str,
        intent_tag: IntentTag,
        related_event_ids: list[str] | None = None,
    ) -> AgentMessage:
        """Create, append, and broadcast a new agent message."""
        async with self._lock:
            message = AgentMessage(
                id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                agent_name=agent_name,
                agent_role=agent_role,
                content=content,
                intent_tag=intent_tag,
                related_event_ids=related_event_ids or [],
            )
            self._messages.append(message)

        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

        return message

    # ── Querying ────────────────────────────────────────────────────

    def get_messages(self, since_index: int = 0) -> list[AgentMessage]:
        """Return messages starting from *since_index*."""
        return self._messages[since_index:]

    # ── SSE Subscription ────────────────────────────────────────────

    async def subscribe(self) -> asyncio.Queue[AgentMessage]:
        queue: asyncio.Queue[AgentMessage] = asyncio.Queue(maxsize=256)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[AgentMessage]) -> None:
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    # ── Lifecycle ───────────────────────────────────────────────────

    def clear(self) -> None:
        """Reset the store for scenario replay."""
        self._messages.clear()
