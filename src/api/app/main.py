"""Supply Closet Replenishment API — FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import config, events, messages, metrics, scenarios, state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
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


@app.get("/health")
async def health():
    """Health check endpoint for ACA probes and smoke tests."""
    return {"status": "ok"}

# Serve static UI build in production (if the directory exists)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
