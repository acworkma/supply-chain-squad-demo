"""Runtime configuration endpoints — model config for eval scripts."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.config_store import runtime_config

router = APIRouter(tags=["config"])


class ConfigUpdate(BaseModel):
    """Request body for PUT /api/config."""

    model_deployment: Optional[str] = None
    agent_model_overrides: Optional[dict[str, str]] = None
    max_output_tokens: Optional[int] = None
    agent_max_tokens_overrides: Optional[dict[str, int]] = None


@router.get("/config")
async def get_config():
    """Return the current effective runtime configuration."""
    return runtime_config.get_config()


@router.put("/config")
async def update_config(body: ConfigUpdate):
    """Update runtime model configuration (no container restart needed)."""
    return await runtime_config.update_config(
        model_deployment=body.model_deployment,
        agent_model_overrides=body.agent_model_overrides,
        max_output_tokens=body.max_output_tokens,
        agent_max_tokens_overrides=body.agent_max_tokens_overrides,
    )


@router.post("/config/reset")
async def reset_config():
    """Reset runtime configuration back to env var defaults."""
    return await runtime_config.reset()
