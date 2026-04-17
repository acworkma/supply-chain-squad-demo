"""Application settings — read from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration for the Supply Closet Replenishment API.

    All values are read from environment variables (case-insensitive).
    """

    # Azure AI Foundry connection — legacy names (backward compat)
    PROJECT_ENDPOINT: str = ""
    PROJECT_CONNECTION_STRING: str = ""

    # Azure AI Foundry connection — Agent Framework convention
    FOUNDRY_PROJECT_ENDPOINT: str = ""
    FOUNDRY_MODEL_DEPLOYMENT_NAME: str = ""

    # Model deployment used by agents (legacy default)
    MODEL_DEPLOYMENT_NAME: str = "gpt-4.1"

    # Maximum output tokens per agent response (controls verbosity)
    MAX_OUTPUT_TOKENS: int = 512

    # Per-agent model overrides — JSON string from env var
    # Example: '{"supply-scanner":"gpt-5-mini","order-manager":"gpt-5-mini"}'
    AGENT_MODEL_OVERRIDES: str = "{}"

    # Per-agent max token overrides — JSON string from env var
    # Example: '{"supply-coordinator":2048,"supply-scanner":512}'
    AGENT_MAX_TOKENS_OVERRIDES: str = "{}"

    # --- Persistent agent registry (ADR-005) ---
    # "persistent" → invoke persistent Foundry agents registered via
    # scripts/build_agents.py. "ephemeral" → legacy in-line instructions via
    # FoundryChatClient (kept for local dev / fallback).
    AGENT_REGISTRY_MODE: str = "persistent"

    # Optional prefix applied to every agent name at registration and lookup
    # time (useful for multi-environment isolation, e.g. "dev-").
    AGENT_NAME_PREFIX: str = ""

    # Optional JSON mapping of agent_name → pinned version (overrides the
    # "latest version" lookup). Example: '{"supply-scanner":"3"}'.
    AGENT_VERSION_OVERRIDES: str = "{}"

    # Azure Monitor / Application Insights connection string for OTel
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""

    # UI theme hint (passed to frontend via /api/state or similar)
    APP_THEME: str = "dark"

    model_config = {"env_prefix": "", "case_sensitive": False}

    @property
    def effective_endpoint(self) -> str:
        """Return the effective Foundry project endpoint (new name preferred)."""
        return self.FOUNDRY_PROJECT_ENDPOINT or self.PROJECT_ENDPOINT

    @property
    def effective_model(self) -> str:
        """Return the effective model deployment name (new name preferred)."""
        return self.FOUNDRY_MODEL_DEPLOYMENT_NAME or self.MODEL_DEPLOYMENT_NAME


settings = Settings()
