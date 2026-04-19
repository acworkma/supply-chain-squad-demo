"""Unit tests for scripts/evals_runner.py.

No network: tests validate request body construction and the soft-fail
behavior of ``trigger_runs`` against a fake client.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make scripts/ importable.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from evals_runner import (  # noqa: E402
    AGENT_PROMPTS,
    EVAL_API_VERSION,
    EvalRunResult,
    bootstrap_enabled,
    build_run_body,
    resolve_eval_id,
    trigger_runs,
)


AGENTS = [
    "supply-coordinator",
    "supply-scanner",
    "catalog-sourcer",
    "order-manager",
    "compliance-gate",
]


def test_every_agent_has_a_prompt() -> None:
    assert set(AGENT_PROMPTS) == set(AGENTS)
    for prompt in AGENT_PROMPTS.values():
        assert len(prompt) > 50  # non-trivial generator instructions


def test_build_run_body_shape() -> None:
    body = build_run_body(
        agent_name="supply-coordinator",
        agent_version="1",
        model_deployment="gpt-5.2",
        samples_count=15,
        dataset_suffix="t1",
    )
    assert body["name"] == "supply-coordinator"
    assert body["metadata"] == {"trigger_type": "oneoff"}

    ds = body["data_source"]
    assert ds["type"] == "azure_ai_synthetic_data_gen_preview"
    assert ds["target"] == {
        "type": "azure_ai_agent",
        "name": "supply-coordinator",
        "version": "1",
        "tool_descriptions": [],
    }

    gen = ds["item_generation_params"]
    assert gen["type"] == "synthetic_data_gen_preview"
    assert gen["samples_count"] == 15
    assert gen["model_deployment_name"] == "gpt-5.2"
    assert gen["output_dataset_name"] == "scdemo-eval-supply-coordinator-t1"
    assert gen["data_mapping"] == {"query": "{{item.query}}"}
    assert gen["sources"] == []
    assert "supply-coordinator" in gen["prompt"].lower()


def test_build_run_body_unknown_agent_raises() -> None:
    with pytest.raises(ValueError, match="No synthetic-gen prompt"):
        build_run_body(
            agent_name="not-a-real-agent",
            agent_version="1",
            model_deployment="gpt-5.2",
            samples_count=5,
            dataset_suffix="x",
        )


def _make_fake_client(responses: list[MagicMock]) -> MagicMock:
    """Return a fake AIProjectClient whose send_request cycles through responses."""
    client = MagicMock()
    client.send_request.side_effect = responses
    return client


def _resp(status: int, body: dict | None = None, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body or {}
    r.text.return_value = text or str(body or "")
    return r


def test_trigger_runs_all_created(monkeypatch) -> None:
    fake_client_cls = MagicMock()
    fake_responses = [
        _resp(201, {"id": f"evalrun_{i}"}) for i in range(5)
    ]
    fake_client_cls.return_value = _make_fake_client(fake_responses)

    monkeypatch.setattr("azure.ai.projects.AIProjectClient", fake_client_cls)

    results = trigger_runs(
        project_endpoint="https://x.example/api/projects/p",
        eval_id="eval_123",
        agent_names=AGENTS,
        model_deployment="gpt-5.2",
        credential=MagicMock(),
    )

    assert len(results) == 5
    assert all(r.status == "created" for r in results)
    assert [r.run_id for r in results] == [f"evalrun_{i}" for i in range(5)]

    # Validate URL construction on first call.
    called_url = fake_client_cls.return_value.send_request.call_args_list[0][0][0].url
    assert called_url.endswith(
        f"/openai/evals/eval_123/runs?api-version={EVAL_API_VERSION}"
    )


def test_trigger_runs_soft_fails_per_agent(monkeypatch) -> None:
    fake_client_cls = MagicMock()
    fake_responses = [
        _resp(201, {"id": "evalrun_ok1"}),
        _resp(500, text="boom"),  # second agent: server error → "failed"
        _resp(201, {"id": "evalrun_ok3"}),
    ]
    fake_client_cls.return_value = _make_fake_client(fake_responses)

    monkeypatch.setattr("azure.ai.projects.AIProjectClient", fake_client_cls)

    results = trigger_runs(
        project_endpoint="https://x.example/api/projects/p",
        eval_id="eval_123",
        agent_names=AGENTS[:3],
        model_deployment="gpt-5.2",
        credential=MagicMock(),
    )

    statuses = [r.status for r in results]
    assert statuses == ["created", "failed", "created"]
    assert results[1].message and "HTTP 500" in results[1].message


def test_trigger_runs_catches_exceptions(monkeypatch) -> None:
    fake_client_cls = MagicMock()
    fake_client = MagicMock()
    fake_client.send_request.side_effect = RuntimeError("network down")
    fake_client_cls.return_value = fake_client
    monkeypatch.setattr("azure.ai.projects.AIProjectClient", fake_client_cls)

    results = trigger_runs(
        project_endpoint="https://x.example/api/projects/p",
        eval_id="eval_123",
        agent_names=["supply-coordinator"],
        model_deployment="gpt-5.2",
        credential=MagicMock(),
    )

    assert len(results) == 1
    assert results[0].status == "failed"
    assert "RuntimeError: network down" in (results[0].message or "")


def test_bootstrap_enabled_defaults_true(monkeypatch) -> None:
    monkeypatch.delenv("FOUNDRY_BOOTSTRAP_EVALS", raising=False)
    assert bootstrap_enabled() is True


@pytest.mark.parametrize("value", ["false", "False", "0", "no", "off", " OFF "])
def test_bootstrap_enabled_opt_out(monkeypatch, value: str) -> None:
    monkeypatch.setenv("FOUNDRY_BOOTSTRAP_EVALS", value)
    assert bootstrap_enabled() is False


def test_resolve_eval_id(monkeypatch) -> None:
    monkeypatch.delenv("FOUNDRY_EVAL_ID", raising=False)
    assert resolve_eval_id() is None
    monkeypatch.setenv("FOUNDRY_EVAL_ID", "  eval_abc123  ")
    assert resolve_eval_id() == "eval_abc123"
    monkeypatch.setenv("FOUNDRY_EVAL_ID", "   ")
    assert resolve_eval_id() is None


def test_eval_run_result_dataclass_fields() -> None:
    r = EvalRunResult(agent_name="x", status="created", run_id="evalrun_1")
    assert r.agent_name == "x"
    assert r.status == "created"
    assert r.run_id == "evalrun_1"
    assert r.message is None
