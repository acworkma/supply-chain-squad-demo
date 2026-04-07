"""Vision-based scenario endpoints — image upload triggers closet detection and workflow."""

import asyncio
import logging
from pathlib import PurePosixPath

from fastapi import APIRouter, BackgroundTasks, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import approval_signal
from app.agents.orchestrator import run_scenario
from app.events import event_store
from app.messages import message_store
from app.metrics import metrics_store
from app.models.enums import IntentTag
from app.models.events import CLOSET_SCAN_INITIATED
from app.state import store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["vision"])

# ── Closet lookup table ─────────────────────────────────────────────

CLOSET_MAP: dict[str, dict] = {
    "icu": {
        "closet_id": "CLO-ICU-01",
        "closet_name": "ICU Main Closet",
        "scenario_type": "routine-restock",
    },
    "or": {
        "closet_id": "CLO-OR-01",
        "closet_name": "OR Supply Room",
        "scenario_type": "routine-restock",
    },
    "nicu": {
        "closet_id": "CLO-NICU-01",
        "closet_name": "NICU Closet",
        "scenario_type": "routine-restock",
    },
    "surgery": {
        "closet_id": "CLO-SURG-01",
        "closet_name": "Med-Surg Closet",
        "scenario_type": "critical-shortage",
    },
    "oncology": {
        "closet_id": "CLO-ONC-01",
        "closet_name": "Oncology Closet",
        "scenario_type": "routine-restock",
    },
}

# Reuse the same lock from scenarios to prevent concurrent runs
_scenario_lock = asyncio.Lock()


async def _wait_for_lock_release(timeout: float = 3.0) -> bool:
    """After signaling an in-flight task, wait briefly for the lock to release."""
    if not _scenario_lock.locked():
        return True
    interval = 0.1
    waited = 0.0
    while waited < timeout:
        await asyncio.sleep(interval)
        if not _scenario_lock.locked():
            return True
        waited += interval
    return False


def _reset_and_seed() -> None:
    """Clear all stores and re-seed the initial closet state."""
    approval_signal.signal()
    store.clear()
    store.seed_initial_state()
    event_store.clear()
    message_store.clear()


# ── POST /scenario/scan-image ───────────────────────────────────────


@router.post("/scenario/scan-image")
async def scan_image(file: UploadFile = File(...)):
    """Receive an uploaded image and detect which supply closet it represents.

    Only the filename matters — actual image content is not analysed in
    simulated mode.  Returns the closet metadata and current inventory items.
    """
    stem = PurePosixPath(file.filename or "").stem.lower()
    match = CLOSET_MAP.get(stem)

    if match is None:
        return JSONResponse(
            status_code=422,
            content={"error": "Supply closet not detected."},
        )

    closet_id = match["closet_id"]

    # Reset and seed so the inventory is fresh
    _reset_and_seed()
    if not await _wait_for_lock_release():
        return JSONResponse(
            status_code=409,
            content={"error": "scenario already running"},
        )

    # Collect SupplyItems belonging to this closet
    items = store.get_items(filter_fn=lambda i: i.closet_id == closet_id)

    return JSONResponse(
        status_code=200,
        content={
            "status": "detected",
            "closet_id": closet_id,
            "closet_name": match["closet_name"],
            "scenario_type": match["scenario_type"],
            "items": [item.model_dump(mode="json") for item in items],
        },
    )


# ── POST /scenario/start-workflow ───────────────────────────────────


class StartWorkflowRequest(BaseModel):
    closet_id: str
    scenario_type: str


@router.post("/scenario/start-workflow")
async def start_workflow(body: StartWorkflowRequest, background_tasks: BackgroundTasks):
    """Begin the orchestration workflow for a previously-detected closet.

    Publishes the initial events/messages and kicks off ``run_scenario``
    in the background.  Returns 202 immediately.
    """
    # Resolve closet metadata from the store (already seeded by scan-image)
    closet = store.get_closet(body.closet_id)
    if closet is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": f"Closet {body.closet_id} not found. Call /scenario/scan-image first."},
        )

    if not await _wait_for_lock_release():
        return JSONResponse(
            status_code=409,
            content={"error": "scenario already running"},
        )

    trigger = "critical_alert" if body.scenario_type == "critical-shortage" else "scheduled"
    intent = IntentTag.ESCALATE if body.scenario_type == "critical-shortage" else IntentTag.PROPOSE

    await event_store.publish(
        event_type=CLOSET_SCAN_INITIATED,
        entity_id=body.closet_id,
        payload={
            "closet_id": body.closet_id,
            "closet_name": closet.name,
            "trigger": trigger,
        },
    )
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content=(
            f"{'URGENT: Critical supply shortage alert' if body.scenario_type == 'critical-shortage' else 'Routine restock scan initiated'} "
            f"for {closet.name} ({body.closet_id}). "
            f"{'Initiating emergency assessment.' if body.scenario_type == 'critical-shortage' else 'Starting supply assessment workflow.'}"
        ),
        intent_tag=intent,
    )

    async def _run():
        async with _scenario_lock:
            try:
                result = await run_scenario(body.scenario_type, store, event_store, message_store)
                logger.info("%s completed: %s", body.scenario_type, result)
                if result.get("metrics"):
                    await metrics_store.record(result["metrics"])
            except Exception:
                logger.exception("%s failed", body.scenario_type)

    background_tasks.add_task(_run)
    return JSONResponse(
        status_code=202,
        content={
            "status": "started",
            "scenario": body.scenario_type,
            "closet_id": body.closet_id,
        },
    )
