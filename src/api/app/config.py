"""Application settings — read from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration for the Supply Closet Replenishment API.

    All values are read from environment variables (case-insensitive).
    """

    # Azure AI Foundry connection — provide one or both
    PROJECT_ENDPOINT: str = ""
    PROJECT_CONNECTION_STRING: str = ""

    # Model deployment used by agents
    MODEL_DEPLOYMENT_NAME: str = "gpt-4.1"

    # Maximum output tokens per agent response (controls verbosity)
    MAX_OUTPUT_TOKENS: int = 1024

    # Per-agent model overrides — JSON string from env var
    # Example: '{"supply-scanner":"gpt-5-mini","order-manager":"gpt-5-mini"}'
    AGENT_MODEL_OVERRIDES: str = "{}"

    # Per-agent max token overrides — JSON string from env var
    # Example: '{"supply-coordinator":2048,"supply-scanner":512}'
    AGENT_MAX_TOKENS_OVERRIDES: str = "{}"

    # UI theme hint (passed to frontend via /api/state or similar)
    APP_THEME: str = "dark"

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
