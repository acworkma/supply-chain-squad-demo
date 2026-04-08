"""Scenario trigger endpoints — start supply-closet replenishment workflows."""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from app import approval_signal
from app.agents.orchestrator import run_scenario
from app.events import event_store
from app.messages import message_store
from app.metrics import metrics_store
from app.models.enums import IntentTag
from app.models.events import CLOSET_SCAN_INITIATED
from app.state import store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scenarios"])

# Mutex to prevent concurrent scenario runs (ADR-007)
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
    approval_signal.signal()  # wake any in-flight approval wait
    store.clear()
    store.seed_initial_state()
    event_store.clear()
    message_store.clear()


# ── routine-restock ─────────────────────────────────────────────────


@router.post("/scenario/routine-restock")
async def run_routine_restock(background_tasks: BackgroundTasks):
    """Trigger a routine restock of the ICU closet.

    Clears state, seeds initial conditions, publishes a scan-initiated event,
    and kicks off orchestration in the background.  Returns 202 immediately.
    """
    _reset_and_seed()
    if not await _wait_for_lock_release():
        return JSONResponse(status_code=409, content={"error": "scenario already running"})

    await event_store.publish(
        event_type=CLOSET_SCAN_INITIATED,
        entity_id="CLO-ICU-01",
        payload={
            "closet_id": "CLO-ICU-01",
            "closet_name": "ICU Main Closet",
            "trigger": "scheduled",
        },
    )
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content=(
            "Routine restock scan initiated for ICU Main Closet (CLO-ICU-01). "
            "Starting supply assessment workflow."
        ),
        intent_tag=IntentTag.PROPOSE,
    )

    async def _run():
        async with _scenario_lock:
            try:
                result = await run_scenario("routine-restock", store, event_store, message_store)
                logger.info("routine-restock completed: %s", result)
                if result.get("metrics"):
                    await metrics_store.record(result["metrics"])
            except Exception:
                logger.exception("routine-restock failed")
                import traceback
                traceback.print_exc()

    background_tasks.add_task(_run)
    return JSONResponse(
        status_code=202,
        content={"status": "started", "scenario": "routine-restock",
                 "closet_id": "CLO-ICU-01"},
    )


# ── critical-shortage ───────────────────────────────────────────────


@router.post("/scenario/critical-shortage")
async def run_critical_shortage(background_tasks: BackgroundTasks):
    """Trigger a critical shortage response for the Med-Surg closet.

    Clears state, seeds initial conditions, publishes a scan-initiated event,
    and kicks off orchestration in the background.  Returns 202 immediately.
    """
    _reset_and_seed()
    if not await _wait_for_lock_release():
        return JSONResponse(status_code=409, content={"error": "scenario already running"})

    await event_store.publish(
        event_type=CLOSET_SCAN_INITIATED,
        entity_id="CLO-SURG-01",
        payload={
            "closet_id": "CLO-SURG-01",
            "closet_name": "Med-Surg Closet",
            "trigger": "critical_alert",
        },
    )
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content=(
            "URGENT: Critical supply shortage alert for Med-Surg Closet (CLO-SURG-01). "
            "Initiating emergency assessment."
        ),
        intent_tag=IntentTag.ESCALATE,
    )

    async def _run():
        async with _scenario_lock:
            try:
                result = await run_scenario("critical-shortage", store, event_store, message_store)
                logger.info("critical-shortage completed: %s", result)
                if result.get("metrics"):
                    await metrics_store.record(result["metrics"])
            except Exception:
                logger.exception("critical-shortage failed")
                import traceback
                traceback.print_exc()

    background_tasks.add_task(_run)
    return JSONResponse(
        status_code=202,
        content={"status": "started", "scenario": "critical-shortage",
                 "closet_id": "CLO-SURG-01"},
    )


# ── seed ────────────────────────────────────────────────────────────


@router.post("/scenario/seed")
async def seed_state():
    """Reset state and seed closets/items without starting orchestration."""
    _reset_and_seed()
    return {"status": "seeded", "closets": len(store.closets), "items": len(store.items)}
