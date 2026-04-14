"""Shared scenario lock — prevents concurrent scenario runs (ADR-007)."""

import asyncio

scenario_lock = asyncio.Lock()
