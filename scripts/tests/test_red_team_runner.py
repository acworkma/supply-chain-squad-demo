"""Unit tests for scripts/red_team_runner.py.

No network: tests validate request body construction and the soft-fail
behavior of ``trigger_red_teams`` against a fake client.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from red_team_runner import (  # noqa: E402
    AGENT_SCENARIOS,
    DEFAULT_ATTACK_STRATEGIES,
    DEFAULT_NUM_TURNS,
    DEFAULT_RISK_CATEGORIES,
    RED_TEAM_API_VERSION,
    RedTeamConfig,
    RedTeamRunResult,
    build_all_configs,
    build_red_team_body,
    trigger_red_teams,
)

AGENTS = [
    "supply-coordinator",
    "supply-scanner",
    "catalog-sourcer",
    "order-manager",
    "compliance-gate",
]


def test_every_agent_has_a_scenario() -> None:
    assert set(AGENT_SCENARIOS) == set(AGENTS)


def test_api_version_is_pinned() -> None:
    assert RED_TEAM_API_VERSION == "2025-11-15-preview"


def test_build_body_basic_shape() -> None:
    body = build_red_team_body(
        agent_name="compliance-gate",
        agent_version="2",
        model_deployment="gpt-4.1",
    )
    assert body["numTurns"] == DEFAULT_NUM_TURNS
    assert body["simulationOnly"] is False
    assert body["attackStrategies"] == list(DEFAULT_ATTACK_STRATEGIES)
    assert body["riskCategories"] == list(DEFAULT_RISK_CATEGORIES)
    assert body["target"] == {
        "type": "AzureOpenAIModel",
        "modelDeploymentName": "gpt-4.1",
    }
    assert "compliance" in body["applicationScenario"].lower()
    assert body["tags"]["agent_name"] == "compliance-gate"
    assert body["tags"]["agent_version"] == "2"
    assert body["id"].startswith("rt-compliance-gate-")
    assert body["displayName"].startswith("redteam-compliance-gate")


def test_build_body_display_suffix_applied() -> None:
    body = build_red_team_body(
        agent_name="supply-scanner",
        agent_version="1",
        model_deployment="gpt-4.1",
        display_name_suffix="20260419",
    )
    assert body["displayName"] == "redteam-supply-scanner-20260419"


def test_build_body_explicit_run_id_preserved() -> None:
    body = build_red_team_body(
        agent_name="order-manager",
        agent_version="1",
        model_deployment="gpt-4.1",
        run_id="rt-custom-id",
    )
    assert body["id"] == "rt-custom-id"


def test_build_body_custom_categories_and_strategies() -> None:
    body = build_red_team_body(
        agent_name="supply-coordinator",
        agent_version="1",
        model_deployment="gpt-4.1",
        risk_categories=["Sexual", "SelfHarm"],
        attack_strategies=["moderate", "jailbreak"],
        num_turns=3,
        simulation_only=True,
    )
    assert body["riskCategories"] == ["Sexual", "SelfHarm"]
    assert body["attackStrategies"] == ["moderate", "jailbreak"]
    assert body["numTurns"] == 3
    assert body["simulationOnly"] is True


def test_build_body_unknown_agent_rejected() -> None:
    with pytest.raises(ValueError, match="No application scenario"):
        build_red_team_body(
            agent_name="phantom-agent",
            agent_version="1",
            model_deployment="gpt-4.1",
        )


def test_build_all_configs_covers_each_agent() -> None:
    configs = build_all_configs(
        agent_names=AGENTS,
        model_deployment="gpt-4.1",
        agent_version="2",
    )
    assert len(configs) == 5
    assert [c.agent_name for c in configs] == AGENTS
    # Every body must carry its own unique id.
    ids = [c.body["id"] for c in configs]
    assert len(set(ids)) == 5


def test_build_all_configs_respects_version_overrides() -> None:
    configs = build_all_configs(
        agent_names=["compliance-gate", "supply-scanner"],
        model_deployment="gpt-4.1",
        agent_version="1",
        agent_versions={"compliance-gate": "5"},
    )
    by_name = {c.agent_name: c for c in configs}
    assert by_name["compliance-gate"].agent_version == "5"
    assert by_name["compliance-gate"].body["tags"]["agent_version"] == "5"
    assert by_name["supply-scanner"].agent_version == "1"


def _make_fake_client(status: int, payload: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.content = b"{}" if payload is None else b"x"
    resp.json.return_value = payload or {}
    resp.text.return_value = "err-body"
    client = MagicMock()
    client.send_request.return_value = resp
    return client


def test_trigger_happy_path_marks_created() -> None:
    cfgs = build_all_configs(
        agent_names=["compliance-gate"],
        model_deployment="gpt-4.1",
    )
    fake = _make_fake_client(201, {"id": "rt-server-assigned"})
    with patch("red_team_runner.AIProjectClient", return_value=fake) if False else patch(
        "azure.ai.projects.AIProjectClient", return_value=fake
    ):
        results = trigger_red_teams(
            project_endpoint="https://example/api/projects/p",
            configs=cfgs,
            credential=MagicMock(),
        )
    assert len(results) == 1
    assert results[0].status == "created"
    assert results[0].run_id == "rt-server-assigned"


def test_trigger_non_2xx_soft_fails() -> None:
    cfgs = build_all_configs(
        agent_names=["order-manager"],
        model_deployment="gpt-4.1",
    )
    fake = _make_fake_client(400, None)
    with patch("azure.ai.projects.AIProjectClient", return_value=fake):
        results = trigger_red_teams(
            project_endpoint="https://example/api/projects/p",
            configs=cfgs,
            credential=MagicMock(),
        )
    assert results[0].status == "failed"
    assert "HTTP 400" in (results[0].message or "")


def test_trigger_exception_soft_fails() -> None:
    cfgs = build_all_configs(
        agent_names=["catalog-sourcer", "supply-scanner"],
        model_deployment="gpt-4.1",
    )
    fake = MagicMock()
    fake.send_request.side_effect = RuntimeError("boom")
    with patch("azure.ai.projects.AIProjectClient", return_value=fake):
        results = trigger_red_teams(
            project_endpoint="https://example/api/projects/p",
            configs=cfgs,
            credential=MagicMock(),
        )
    assert len(results) == 2
    assert all(r.status == "failed" for r in results)
    assert all("RuntimeError: boom" in (r.message or "") for r in results)


def test_trigger_hits_correct_url() -> None:
    cfgs = build_all_configs(
        agent_names=["compliance-gate"],
        model_deployment="gpt-4.1",
    )
    fake = _make_fake_client(201, {"id": "x"})
    with patch("azure.ai.projects.AIProjectClient", return_value=fake):
        trigger_red_teams(
            project_endpoint="https://example/api/projects/p",
            configs=cfgs,
            credential=MagicMock(),
        )
    call_args = fake.send_request.call_args
    request = call_args[0][0]
    assert "redTeams/runs:run" in request.url
    assert RED_TEAM_API_VERSION in request.url
