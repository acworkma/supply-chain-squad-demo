"""Unit tests for persistent agent registry (agents/registry.py)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents import registry


# ── Fingerprint helpers ──────────────────────────────────────────────


def test_definition_fingerprint_is_stable():
    """Same definition → same fingerprint; different definition → different fingerprint."""
    d1 = registry._build_agent_definition("supply-scanner", "gpt-4.1")
    d2 = registry._build_agent_definition("supply-scanner", "gpt-4.1")
    d3 = registry._build_agent_definition("supply-scanner", "gpt-5-mini")

    assert registry._definition_fingerprint(d1) == registry._definition_fingerprint(d2)
    assert registry._definition_fingerprint(d1) != registry._definition_fingerprint(d3)


def test_build_agent_definition_uses_prompt_file():
    """The definition's instructions must match the on-disk prompt file verbatim."""
    expected = registry._load_prompt("supply-scanner")
    defn = registry._build_agent_definition("supply-scanner", "gpt-4.1")
    assert defn.instructions == expected
    # Supply scanner has 2 tools registered
    assert len(defn.tools) == 2


def test_agent_names_covers_all_five():
    assert set(registry.AGENT_NAMES) == {
        "supply-coordinator",
        "supply-scanner",
        "catalog-sourcer",
        "order-manager",
        "compliance-gate",
    }


# ── sync_agent behavior ──────────────────────────────────────────────


def _mock_client_with_existing(fingerprints: dict[str, str]) -> MagicMock:
    """Build a MagicMock ``AIProjectClient`` whose ``list_versions`` yields
    versions matching the supplied ``{version_id: fingerprint}`` map."""
    client = MagicMock()

    async def _fake_list_versions(agent_name):
        for ver_id, _ in fingerprints.items():
            # Async generator protocol
            defn_mock = MagicMock()
            defn_mock.as_dict.return_value = {"fake": ver_id}  # deterministic but
            # The fingerprint is computed from the returned dict; we don't need
            # to match a real one unless the test asserts "unchanged". In that
            # case we provide the fingerprint directly via monkeypatch below.
            yield SimpleNamespace(version=ver_id, definition=defn_mock)

    client.agents.list_versions = _fake_list_versions
    client.agents.create_version = AsyncMock(
        return_value=SimpleNamespace(version="42"),
    )
    return client


@pytest.mark.asyncio
async def test_sync_agent_creates_when_no_versions_exist(monkeypatch):
    """If ``list_versions`` yields nothing → call ``create_version``."""
    client = MagicMock()

    async def _empty_list_versions(agent_name):
        return
        yield  # make it an async generator

    client.agents.list_versions = _empty_list_versions
    client.agents.create_version = AsyncMock(
        return_value=SimpleNamespace(version="1"),
    )

    reg = await registry.sync_agent(client, "supply-scanner", "gpt-4.1")
    assert reg.status == "created"
    assert reg.version == "1"
    client.agents.create_version.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_agent_unchanged_when_fingerprint_matches(monkeypatch):
    """If an existing version has matching fingerprint → no create_version call."""
    target_defn = registry._build_agent_definition("supply-scanner", "gpt-4.1")
    target_fp = registry._definition_fingerprint(target_defn)

    # Monkeypatch _existing_fingerprints to return our target fingerprint
    async def _fake_existing(_client, _agent):
        return {"3": target_fp, "2": "other"}

    monkeypatch.setattr(registry, "_existing_fingerprints", _fake_existing)

    client = MagicMock()
    client.agents.create_version = AsyncMock()

    reg = await registry.sync_agent(client, "supply-scanner", "gpt-4.1")
    assert reg.status == "unchanged"
    assert reg.version == "3"  # newest (max of "2","3")
    client.agents.create_version.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_agent_updates_when_fingerprint_differs(monkeypatch):
    """If existing versions don't match the new fingerprint → create new version."""

    async def _fake_existing(_client, _agent):
        return {"1": "old-fingerprint", "2": "also-old"}

    monkeypatch.setattr(registry, "_existing_fingerprints", _fake_existing)

    client = MagicMock()
    client.agents.create_version = AsyncMock(
        return_value=SimpleNamespace(version="3"),
    )

    reg = await registry.sync_agent(client, "supply-scanner", "gpt-4.1")
    assert reg.status == "updated"
    assert reg.version == "3"
    client.agents.create_version.assert_awaited_once()
