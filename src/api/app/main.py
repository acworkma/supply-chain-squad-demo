"""Supply Closet Replenishment API — FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import approval, config, events, messages, metrics, scenarios, state, vision


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    import logging

    logger = logging.getLogger(__name__)

    # Initialize OpenTelemetry if App Insights connection string is available
    from app.config import settings as app_settings

    if app_settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=app_settings.APPLICATIONINSIGHTS_CONNECTION_STRING,
        )

    # Initialize Agent Framework tracing (built-in OTel support)
    try:
        from agent_framework.observability import configure_otel_providers

        configure_otel_providers(enable_sensitive_data=False)
    except ImportError:
        pass  # Agent Framework not installed (dev mode)

    # Log the agent registry mode so it's visible in startup logs.
    logger.info(
        "agent_registry_mode=%s name_prefix=%r",
        app_settings.AGENT_REGISTRY_MODE,
        app_settings.AGENT_NAME_PREFIX,
    )

    # In persistent mode, resolve agent versions once at startup so a missing
    # registration fails loudly here (not on first scenario run).
    if (
        app_settings.AGENT_REGISTRY_MODE.lower() == "persistent"
        and app_settings.effective_endpoint
    ):
        try:
            from azure.identity.aio import DefaultAzureCredential

            from app.agents.registry import AGENT_NAMES, resolve_agent_versions

            prefix = app_settings.AGENT_NAME_PREFIX or ""
            names = [f"{prefix}{n}" for n in AGENT_NAMES]
            credential = DefaultAzureCredential()
            try:
                versions = await resolve_agent_versions(
                    endpoint=app_settings.effective_endpoint,
                    credential=credential,
                    agent_names=names,
                )
                logger.info("Resolved persistent agent versions at startup: %s", versions)
            finally:
                await credential.close()
        except Exception as exc:
            # Don't crash the app — log and continue. The orchestrator will
            # re-attempt resolution on the first scenario request.
            logger.warning("Could not pre-resolve agent versions at startup: %s", exc)

    from app.state import store

    store.seed_initial_state()
    yield


app = FastAPI(
    title="Supply Closet Replenishment API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(state.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(scenarios.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(approval.router, prefix="/api")
app.include_router(vision.router, prefix="/api")


@app.get("/health")
async def health():
    """Health check endpoint for ACA probes and smoke tests."""
    return {"status": "ok"}

# Serve static UI build in production (if the directory exists)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(static_dir),
              html=True), name="static")
