"""Runtime configuration store — mutable overlay on top of env var settings.

Follows the asyncio.Lock singleton pattern used by EventStore, MetricsStore,
and StateStore (ADR-001).  The orchestrator reads from here first, falling
back to environment-variable defaults when no runtime override is set.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .config import settings


class RuntimeConfigStore:
    """Thread-safe, in-memory runtime configuration overlay."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._model_deployment: str | None = None
        self._agent_model_overrides: dict[str, str] | None = None
        self._max_output_tokens: int | None = None
        self._agent_max_tokens_overrides: dict[str, int] | None = None

    # ── Read ────────────────────────────────────────────────────────

    def get_config(self) -> dict[str, Any]:
        """Return the effective configuration (runtime overrides + env defaults)."""
        return {
            "model_deployment": (
                self._model_deployment
                if self._model_deployment is not None
                else settings.MODEL_DEPLOYMENT_NAME
            ),
            "agent_model_overrides": (
                self._agent_model_overrides
                if self._agent_model_overrides is not None
                else _parse_json(settings.AGENT_MODEL_OVERRIDES)
            ),
            "max_output_tokens": (
                self._max_output_tokens
                if self._max_output_tokens is not None
                else settings.MAX_OUTPUT_TOKENS
            ),
            "agent_max_tokens_overrides": (
                self._agent_max_tokens_overrides
                if self._agent_max_tokens_overrides is not None
                else _parse_json(settings.AGENT_MAX_TOKENS_OVERRIDES)
            ),
            "live_mode": bool(
                settings.PROJECT_ENDPOINT or settings.PROJECT_CONNECTION_STRING
            ),
        }

    # ── Mutate ──────────────────────────────────────────────────────

    async def update_config(
        self,
        *,
        model_deployment: str | None = None,
        agent_model_overrides: dict[str, str] | None = None,
        max_output_tokens: int | None = None,
        agent_max_tokens_overrides: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """Apply runtime overrides. Only non-None values are updated."""
        async with self._lock:
            if model_deployment is not None:
                self._model_deployment = model_deployment
            if agent_model_overrides is not None:
                self._agent_model_overrides = agent_model_overrides
            if max_output_tokens is not None:
                self._max_output_tokens = max_output_tokens
            if agent_max_tokens_overrides is not None:
                self._agent_max_tokens_overrides = agent_max_tokens_overrides
        return self.get_config()

    async def reset(self) -> dict[str, Any]:
        """Clear all runtime overrides, reverting to env var defaults."""
        async with self._lock:
            self._model_deployment = None
            self._agent_model_overrides = None
            self._max_output_tokens = None
            self._agent_max_tokens_overrides = None
        return self.get_config()

    def clear(self) -> None:
        """Synchronous reset — used by tests."""
        self._model_deployment = None
        self._agent_model_overrides = None
        self._max_output_tokens = None
        self._agent_max_tokens_overrides = None


def _parse_json(value: str) -> dict:
    """Safely parse a JSON string, returning empty dict on failure."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


# Singleton instance
runtime_config = RuntimeConfigStore()
