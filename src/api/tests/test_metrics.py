"""
Metrics store and endpoint tests — record, retrieve, and expose scenario run metrics.
"""

import pytest

from httpx import AsyncClient

from app.metrics.metrics_store import MetricsStore


SAMPLE_METRICS = {
    "total_latency_seconds": 1.234,
    "total_input_tokens": 500,
    "total_output_tokens": 200,
    "agents": [
        {
            "agent_name": "supply-coordinator",
            "model": "simulated",
            "input_tokens": 300,
            "output_tokens": 100,
            "rounds": 1,
            "latency_seconds": 0.5,
        },
        {
            "agent_name": "order-manager",
            "model": "simulated",
            "input_tokens": 200,
            "output_tokens": 100,
            "rounds": 1,
            "latency_seconds": 0.734,
        },
    ],
}


# ===================================================================
# MetricsStore unit tests
# ===================================================================

class TestMetricsStore:

    async def test_get_latest_returns_none_when_empty(self, metrics_store: MetricsStore):
        assert metrics_store.get_latest() is None

    async def test_get_history_returns_empty_list_when_empty(self, metrics_store: MetricsStore):
        assert metrics_store.get_history() == []

    async def test_record_and_get_latest(self, metrics_store: MetricsStore):
        await metrics_store.record(SAMPLE_METRICS)
        latest = metrics_store.get_latest()
        assert latest is not None
        assert latest["total_latency_seconds"] == 1.234
        assert latest["total_input_tokens"] == 500
        assert "recorded_at" in latest

    async def test_get_history_returns_most_recent_first(self, metrics_store: MetricsStore):
        await metrics_store.record({"total_latency_seconds": 1.0, "total_input_tokens": 100, "total_output_tokens": 50, "agents": []})
        await metrics_store.record({"total_latency_seconds": 2.0, "total_input_tokens": 200, "total_output_tokens": 100, "agents": []})
        history = metrics_store.get_history()
        assert len(history) == 2
        assert history[0]["total_latency_seconds"] == 2.0
        assert history[1]["total_latency_seconds"] == 1.0

    async def test_get_history_respects_limit(self, metrics_store: MetricsStore):
        for i in range(5):
            await metrics_store.record({"total_latency_seconds": float(i), "total_input_tokens": i, "total_output_tokens": i, "agents": []})
        history = metrics_store.get_history(limit=3)
        assert len(history) == 3
        assert history[0]["total_latency_seconds"] == 4.0

    async def test_clear_removes_all(self, metrics_store: MetricsStore):
        await metrics_store.record(SAMPLE_METRICS)
        metrics_store.clear()
        assert metrics_store.get_latest() is None
        assert metrics_store.get_history() == []


# ===================================================================
# GET /api/metrics
# ===================================================================

class TestMetricsEndpoint:

    async def test_metrics_returns_200_when_empty(self, test_client: AsyncClient):
        resp = await test_client.get("/api/metrics")
        assert resp.status_code == 200
        assert resp.json()["message"] == "No scenario runs recorded yet"

    async def test_metrics_returns_data_after_recording(self, test_client: AsyncClient):
        from app.metrics import metrics_store
        await metrics_store.record(SAMPLE_METRICS)
        resp = await test_client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_latency_seconds"] == 1.234
        assert data["total_input_tokens"] == 500
        assert "recorded_at" in data


# ===================================================================
# GET /api/metrics/history
# ===================================================================

class TestMetricsHistoryEndpoint:

    async def test_history_returns_200_when_empty(self, test_client: AsyncClient):
        resp = await test_client.get("/api/metrics/history")
        assert resp.status_code == 200
        assert resp.json()["message"] == "No scenario runs recorded yet"

    async def test_history_returns_data_after_recording(self, test_client: AsyncClient):
        from app.metrics import metrics_store
        await metrics_store.record(SAMPLE_METRICS)
        resp = await test_client.get("/api/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["total_latency_seconds"] == 1.234

    async def test_history_limit_parameter(self, test_client: AsyncClient):
        from app.metrics import metrics_store
        for i in range(5):
            await metrics_store.record({"total_latency_seconds": float(i), "total_input_tokens": i, "total_output_tokens": i, "agents": []})
        resp = await test_client.get("/api/metrics/history?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["total_latency_seconds"] == 4.0
