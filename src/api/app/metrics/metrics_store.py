"""In-memory store for scenario run metrics."""

import asyncio
from datetime import datetime, timezone


class MetricsStore:
    """Thread-safe, in-memory store for scenario run metrics.

    Follows the same asyncio.Lock pattern as EventStore and StateStore.
    """

    def __init__(self) -> None:
        self._history: list[dict] = []
        self._lock: asyncio.Lock = asyncio.Lock()

    async def record(self, metrics_dict: dict) -> dict:
        """Store a scenario run's metrics. Returns the recorded entry."""
        async with self._lock:
            entry = {
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                **metrics_dict,
            }
            self._history.append(entry)
            return entry

    def get_latest(self) -> dict | None:
        """Return the most recent run metrics, or None if empty."""
        return self._history[-1] if self._history else None

    def get_history(self, limit: int = 10) -> list[dict]:
        """Return the last *limit* run metrics, most recent first."""
        return list(reversed(self._history[-limit:]))

    def clear(self) -> None:
        """Remove all recorded metrics."""
        self._history.clear()
