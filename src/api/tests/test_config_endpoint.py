"""Tests for the runtime configuration endpoint (GET/PUT /api/config, POST /api/config/reset)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.config_store import RuntimeConfigStore, runtime_config
from app.main import app


# ---------------------------------------------------------------------------
# Fixture: clear runtime config singleton between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_runtime_config():
    """Ensure each test starts with a clean runtime config."""
    runtime_config.clear()
    yield
    runtime_config.clear()


@pytest.fixture
def config_store() -> RuntimeConfigStore:
    """Standalone RuntimeConfigStore for unit tests."""
    return RuntimeConfigStore()


# ---------------------------------------------------------------------------
# Unit tests — RuntimeConfigStore
# ---------------------------------------------------------------------------

class TestRuntimeConfigStore:
    """Direct unit tests for the store logic (no HTTP)."""

    def test_defaults_match_settings(self, config_store: RuntimeConfigStore):
        cfg = config_store.get_config()
        assert cfg["model_deployment"] == settings.MODEL_DEPLOYMENT_NAME
        assert cfg["max_output_tokens"] == settings.MAX_OUTPUT_TOKENS
        assert isinstance(cfg["agent_model_overrides"], dict)
        assert isinstance(cfg["agent_max_tokens_overrides"], dict)
        assert isinstance(cfg["live_mode"], bool)

    @pytest.mark.asyncio
    async def test_update_model_deployment(self, config_store: RuntimeConfigStore):
        result = await config_store.update_config(model_deployment="gpt-4o")
        assert result["model_deployment"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_update_agent_model_overrides(self, config_store: RuntimeConfigStore):
        overrides = {"evs-tasking": "gpt-4o-mini"}
        result = await config_store.update_config(agent_model_overrides=overrides)
        assert result["agent_model_overrides"] == overrides

    @pytest.mark.asyncio
    async def test_update_max_output_tokens(self, config_store: RuntimeConfigStore):
        result = await config_store.update_config(max_output_tokens=2048)
        assert result["max_output_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_update_agent_max_tokens_overrides(self, config_store: RuntimeConfigStore):
        overrides = {"bed-coordinator": 4096}
        result = await config_store.update_config(agent_max_tokens_overrides=overrides)
        assert result["agent_max_tokens_overrides"] == overrides

    @pytest.mark.asyncio
    async def test_partial_update_preserves_other_fields(self, config_store: RuntimeConfigStore):
        await config_store.update_config(model_deployment="gpt-4o")
        result = await config_store.update_config(max_output_tokens=512)
        assert result["model_deployment"] == "gpt-4o"
        assert result["max_output_tokens"] == 512

    @pytest.mark.asyncio
    async def test_reset_clears_overrides(self, config_store: RuntimeConfigStore):
        await config_store.update_config(
            model_deployment="gpt-4o",
            max_output_tokens=2048,
            agent_model_overrides={"evs-tasking": "gpt-4o-mini"},
        )
        result = await config_store.reset()
        assert result["model_deployment"] == settings.MODEL_DEPLOYMENT_NAME
        assert result["max_output_tokens"] == settings.MAX_OUTPUT_TOKENS

    def test_clear_is_synchronous(self, config_store: RuntimeConfigStore):
        config_store._model_deployment = "test"
        config_store.clear()
        assert config_store.get_config()["model_deployment"] == settings.MODEL_DEPLOYMENT_NAME


# ---------------------------------------------------------------------------
# Endpoint tests — HTTP via AsyncClient
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestConfigEndpoints:
    """Integration tests for /api/config endpoints."""

    @pytest.mark.asyncio
    async def test_get_returns_defaults(self, client: AsyncClient):
        resp = await client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_deployment"] == settings.MODEL_DEPLOYMENT_NAME
        assert data["max_output_tokens"] == settings.MAX_OUTPUT_TOKENS
        assert "live_mode" in data
        assert isinstance(data["agent_model_overrides"], dict)
        assert isinstance(data["agent_max_tokens_overrides"], dict)

    @pytest.mark.asyncio
    async def test_put_updates_config(self, client: AsyncClient):
        resp = await client.put("/api/config", json={
            "model_deployment": "gpt-4o",
            "max_output_tokens": 2048,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_deployment"] == "gpt-4o"
        assert data["max_output_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_put_partial_update(self, client: AsyncClient):
        await client.put("/api/config", json={"model_deployment": "gpt-4o"})
        resp = await client.put("/api/config", json={"max_output_tokens": 512})
        data = resp.json()
        assert data["model_deployment"] == "gpt-4o"
        assert data["max_output_tokens"] == 512

    @pytest.mark.asyncio
    async def test_put_agent_model_overrides(self, client: AsyncClient):
        overrides = {"evs-tasking": "gpt-4o-mini", "transport-ops": "gpt-4o-mini"}
        resp = await client.put("/api/config", json={
            "agent_model_overrides": overrides,
        })
        assert resp.status_code == 200
        assert resp.json()["agent_model_overrides"] == overrides

    @pytest.mark.asyncio
    async def test_put_agent_max_tokens_overrides(self, client: AsyncClient):
        overrides = {"bed-coordinator": 4096}
        resp = await client.put("/api/config", json={
            "agent_max_tokens_overrides": overrides,
        })
        assert resp.status_code == 200
        assert resp.json()["agent_max_tokens_overrides"] == overrides

    @pytest.mark.asyncio
    async def test_put_empty_body_is_noop(self, client: AsyncClient):
        resp = await client.put("/api/config", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_deployment"] == settings.MODEL_DEPLOYMENT_NAME

    @pytest.mark.asyncio
    async def test_reset_reverts_to_defaults(self, client: AsyncClient):
        await client.put("/api/config", json={
            "model_deployment": "gpt-4o",
            "max_output_tokens": 99,
        })
        resp = await client.post("/api/config/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_deployment"] == settings.MODEL_DEPLOYMENT_NAME
        assert data["max_output_tokens"] == settings.MAX_OUTPUT_TOKENS

    @pytest.mark.asyncio
    async def test_get_reflects_put(self, client: AsyncClient):
        await client.put("/api/config", json={"model_deployment": "custom-model"})
        resp = await client.get("/api/config")
        assert resp.json()["model_deployment"] == "custom-model"

    @pytest.mark.asyncio
    async def test_get_after_reset(self, client: AsyncClient):
        await client.put("/api/config", json={"model_deployment": "custom-model"})
        await client.post("/api/config/reset")
        resp = await client.get("/api/config")
        assert resp.json()["model_deployment"] == settings.MODEL_DEPLOYMENT_NAME
