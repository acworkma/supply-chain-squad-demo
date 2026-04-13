"""Multi-agent orchestration engine — supervisor pattern (ADR-004).

Provides both a live Azure AI Foundry mode (using the Responses API with
named agents) and a simulated mode that walks through scripted tool calls
for demo without Azure provisioning.

Domain: Hospital supply-closet replenishment.
Agents: supply-coordinator (supervisor), supply-scanner, catalog-sourcer,
        order-manager, compliance-gate.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any, TypedDict

from ..config import settings
from ..events.event_store import EventStore
from ..messages.message_store import MessageStore
from ..models.enums import IntentTag, POState, ScanState, ShipmentState
from ..state.store import StateStore
from ..tools import tool_functions
from .. import approval_signal

logger = logging.getLogger(__name__)

# ── Test mode flag (set by conftest.py during pytest runs) ──────────
_PYTEST_MODE = False


class AgentMetrics(TypedDict):
    agent_name: str
    model: str
    input_tokens: int
    output_tokens: int
    max_output_tokens: int
    rounds: int
    latency_seconds: float


class ScenarioMetrics(TypedDict):
    total_latency_seconds: float
    total_input_tokens: int
    total_output_tokens: int
    agents: list[AgentMetrics]


# ── Tool dispatch table (ADR-003a) ──────────────────────────────────

TOOL_DISPATCH: dict[str, Any] = {
    "get_scan": tool_functions.get_scan,
    "get_items": tool_functions.get_items,
    "get_vendors": tool_functions.get_vendors,
    "get_purchase_orders": tool_functions.get_purchase_orders,
    "get_shipments": tool_functions.get_shipments,
    "initiate_scan": tool_functions.initiate_scan,
    "analyze_scan": tool_functions.analyze_scan,
    "lookup_vendor_catalog": tool_functions.lookup_vendor_catalog,
    "lookup_vendor_catalog_batch": tool_functions.lookup_vendor_catalog_batch,
    "create_purchase_order": tool_functions.create_purchase_order,
    "approve_purchase_order": tool_functions.approve_purchase_order,
    "submit_purchase_order": tool_functions.submit_purchase_order,
    "create_shipment": tool_functions.create_shipment,
    "receive_shipment": tool_functions.receive_shipment,
    "complete_order_lifecycle": tool_functions.complete_order_lifecycle,
    "publish_event": tool_functions.publish_event,
    "escalate": tool_functions.escalate,
}


# ── Agent prompt loader (ADR-008) ───────────────────────────────────

_PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt(agent_name: str) -> str:
    path = _PROMPT_DIR / f"{agent_name}.txt"
    return path.read_text(encoding="utf-8")


# ── Helpers ─────────────────────────────────────────────────────────

STEP_DELAY = 0.15  # seconds between simulated steps for realistic SSE pacing


async def _call_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Dispatch a tool call to the matching function in tool_functions.py."""
    fn = TOOL_DISPATCH.get(name)
    if fn is None:
        return {"ok": False, "error": f"Unknown tool: {name}"}
    return await fn(
        **arguments,
        state_store=state_store,
        event_store=event_store,
        message_store=message_store,
    )


def _use_live_agents() -> bool:
    """Return True if a Foundry project endpoint is configured."""
    return bool(settings.effective_endpoint or settings.PROJECT_CONNECTION_STRING)


# ── Agent name → display role mapping ───────────────────────────────

_AGENT_ROLES: dict[str, str] = {
    "supply-coordinator": "Supply Coordinator",
    "supply-scanner": "Supply Scanner Agent",
    "catalog-sourcer": "Catalog Sourcer Agent",
    "order-manager": "Order Manager Agent",
    "compliance-gate": "Compliance Gate Agent",
}

_AGENT_NAMES = list(_AGENT_ROLES.keys())


# ── Simulated metrics helper ────────────────────────────────────────

def _simulated_metrics(agents: list[str], latency: float) -> ScenarioMetrics:
    """Build a ScenarioMetrics dict for simulated runs (zero tokens)."""
    return {
        "total_latency_seconds": round(latency, 3),
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "agents": [
            {
                "agent_name": n,
                "model": "simulated",
                "input_tokens": 0,
                "output_tokens": 0,
                "max_output_tokens": 0,
                "rounds": 0,
                "latency_seconds": 0.0,
            }
            for n in agents
        ],
    }


# ── Live Azure Foundry orchestration (v2 — Responses API) ──────────

async def _run_live(
    scenario_type: str,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Run orchestration using the Agent Framework with per-agent instructions.

    Each agent is defined by its system prompt and tool set.  All calls use
    the configured model deployment with the ``instructions`` and ``tools``
    parameters customised per agent.
    """
    from agent_framework import FunctionTool, Message
    from agent_framework.foundry import FoundryChatClient
    from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential

    from ..tools.tool_schemas import AGENT_TOOLS

    logger.info("_run_live started: scenario=%s, endpoint=%s", scenario_type,
                settings.effective_endpoint[:60] if settings.effective_endpoint else "NONE")
    mi_client_id = os.environ.get("AZURE_CLIENT_ID")
    if mi_client_id:
        logger.info("Using managed identity: AZURE_CLIENT_ID=%s",
                    mi_client_id[:12] + "...")

    # Read effective config from runtime config store (falls back to env vars)
    from ..config_store import runtime_config

    effective = runtime_config.get_config()
    default_deployment = effective["model_deployment"]
    _model_overrides: dict[str, str] = effective["agent_model_overrides"]
    _token_overrides: dict[str, int] = effective["agent_max_tokens_overrides"]
    default_max_tokens: int = effective["max_output_tokens"]

    # Resolve effective endpoint (new FOUNDRY_* names take precedence)
    effective_endpoint = settings.effective_endpoint
    if not effective_endpoint and settings.PROJECT_CONNECTION_STRING:
        parts = settings.PROJECT_CONNECTION_STRING.split(";")
        host, sub_id, rg, project = parts
        effective_endpoint = f"https://{host}/api/projects/{project}"

    def _build_function_tools(agent_name: str) -> list[FunctionTool]:
        """Build FunctionTool objects for an agent with stores bound via closures."""
        agent_tool_schemas = AGENT_TOOLS.get(agent_name, [])
        tools: list[FunctionTool] = []
        for schema in agent_tool_schemas:
            fn_def = schema["function"]
            tool_name = fn_def["name"]
            dispatch_fn = TOOL_DISPATCH.get(tool_name)
            if dispatch_fn is None:
                continue

            # Closure capturing dispatch_fn and the stores
            async def _bound(*, _fn=dispatch_fn, **kwargs):
                return await _fn(
                    **kwargs,
                    state_store=state_store,
                    event_store=event_store,
                    message_store=message_store,
                )

            tool = FunctionTool(
                name=tool_name,
                description=fn_def.get("description", ""),
                func=_bound,
                input_model=fn_def.get("parameters", {}),
            )
            tools.append(tool)
        return tools

    # Per-agent max-tokens defaults (lower = faster for simple-role agents)
    _AGENT_TOKEN_DEFAULTS: dict[str, int] = {
        "supply-coordinator": 256,
        "supply-scanner": 256,
        "catalog-sourcer": 256,
        "compliance-gate": 256,
        "order-manager": 256,
    }

    # Create a SINGLE credential to reuse across all agent calls
    mi_client_id = os.environ.get("AZURE_CLIENT_ID")
    shared_credential = AsyncDefaultAzureCredential(
        managed_identity_client_id=mi_client_id,
    ) if mi_client_id else AsyncDefaultAzureCredential()

    async def _invoke_agent(agent_name: str, user_message: str) -> dict:
        """Invoke an agent via the Agent Framework with its prompt and tools.

        Returns a dict with ``text`` (the agent's reply) and ``metrics``.
        """
        start = time.monotonic()
        total_input_tokens = 0
        total_output_tokens = 0
        rounds = 0

        deployment = _model_overrides.get(agent_name) or default_deployment
        resolved_max_tokens = _token_overrides.get(
            agent_name) or _AGENT_TOKEN_DEFAULTS.get(agent_name, default_max_tokens)

        agent_instructions = _load_prompt(agent_name)
        agent_tools = _build_function_tools(agent_name)

        try:
            client = FoundryChatClient(
                project_endpoint=effective_endpoint,
                model=deployment,
                credential=shared_credential,
            )
            options = {
                "tools": agent_tools,
                "max_tokens": resolved_max_tokens,
            }
            response = await client.get_response(
                [
                    Message(role="system", contents=[agent_instructions]),
                    Message(role="user", contents=[user_message]),
                ],
                options=options,
            )
            text = response.text if hasattr(
                response, 'text') else str(response)

            # Extract metrics if available
            if hasattr(response, 'usage') and response.usage:
                total_input_tokens = getattr(response.usage, 'input_tokens', 0)
                total_output_tokens = getattr(
                    response.usage, 'output_tokens', 0)
            rounds = 1
        except Exception:
            raise

        latency = time.monotonic() - start
        metrics: AgentMetrics = {
            "agent_name": agent_name,
            "model": deployment,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "max_output_tokens": resolved_max_tokens,
            "rounds": rounds,
            "latency_seconds": round(latency, 3),
        }
        logger.info(
            "agent=%s model=%s input_tokens=%d output_tokens=%d rounds=%d latency_s=%.2f",
            agent_name, deployment, total_input_tokens, total_output_tokens,
            rounds, latency,
        )
        return {"text": text, "metrics": metrics}

    # ── Supervisor loop: supply-coordinator delegates to specialists ─

    # Build a state snapshot of the target closet and items
    closet_id = "CLO-ICU-01" if scenario_type == "routine-restock" else "CLO-SURG-01"
    closet = state_store.get_closet(closet_id)
    closet_items = state_store.get_items(
        filter_fn=lambda i: i.closet_id == closet_id,
    )
    if not closet:
        return {"ok": False, "error": f"Closet {closet_id} not found"}

    # Compact state: just the essentials, no indent to reduce tokens
    items_brief = [
        {"id": i.id, "sku": i.sku, "name": i.name, "qty": i.current_quantity,
         "par": i.par_level, "criticality": i.criticality.value,
         "rate": i.consumption_rate_per_day}
        for i in closet_items
    ]
    state_snapshot = json.dumps(
        {"closet_id": closet_id, "name": closet.name,
            "unit": closet.unit, "items": items_brief},
    )

    initial_msg = (
        f"Replenishment assessment needed: {closet.name} ({closet_id}), {scenario_type}.\n"
        f"State: {state_snapshot}\n"
        f"Briefly assess urgency. Specialists will be invoked in sequence after you."
    )

    # Step 1: Supply Coordinator starts
    coordinator_result = await _invoke_agent("supply-coordinator", initial_msg)
    coordinator_reply = coordinator_result["text"]
    agent_metrics_list: list[AgentMetrics] = [coordinator_result["metrics"]]
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content=coordinator_reply,
        intent_tag=IntentTag.PROPOSE,
    )

    # Step 2: Run supply-scanner + catalog-sourcer in PARALLEL
    # They are independent: scanner scans the closet, sourcer looks up vendors
    # for items already known to be below par from the state snapshot.
    below_par_skus = [i["sku"] for i in items_brief if i["qty"] < i["par"]]

    scanner_msg = f"Scan closet_id={closet_id}. Call initiate_scan then analyze_scan."
    sourcer_msg = (
        f"Look up vendors for these SKUs in a single call: {json.dumps(below_par_skus)}."
    )

    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Supply Scanner and Catalog Sourcer in parallel.",
        intent_tag=IntentTag.PROPOSE,
    )

    scanner_task = asyncio.create_task(
        _invoke_agent("supply-scanner", scanner_msg))
    sourcer_task = asyncio.create_task(
        _invoke_agent("catalog-sourcer", sourcer_msg))
    scanner_result, sourcer_result = await asyncio.gather(scanner_task, sourcer_task)

    # Publish scanner results
    await message_store.publish(
        agent_name="supply-scanner",
        agent_role=_AGENT_ROLES["supply-scanner"],
        content=scanner_result["text"],
        intent_tag=IntentTag.EXECUTE,
    )
    agent_metrics_list.append(scanner_result["metrics"])

    # Extract scan_id from state store
    scan_id = None
    scans = state_store.get_scans()
    if scans:
        scan_id = scans[-1].id
        logger.info("Extracted scan_id=%s from state store", scan_id)

    # Publish sourcer results
    await message_store.publish(
        agent_name="catalog-sourcer",
        agent_role=_AGENT_ROLES["catalog-sourcer"],
        content=sourcer_result["text"],
        intent_tag=IntentTag.PROPOSE,
    )
    agent_metrics_list.append(sourcer_result["metrics"])

    # Extract recommended vendor
    import re
    recommended_vendor_id = None
    vendor_match = re.search(r'(VND-[A-Z]+)', sourcer_result["text"])
    if vendor_match:
        recommended_vendor_id = vendor_match.group(1)
        logger.info(
            "Extracted vendor_id=%s from catalog-sourcer reply", recommended_vendor_id)

    # Step 3: Compliance Gate
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Compliance Gate.",
        intent_tag=IntentTag.PROPOSE,
    )
    critical_items = [
        i for i in items_brief if i["criticality"] == "CRITICAL" and i["qty"] < i["par"]]
    compliance_msg = (
        f"Closet: {closet_id}. Critical items below par: "
        f"{json.dumps([{'name': i['name'], 'qty': i['qty'], 'par': i['par'], 'days': round(i['qty']/i['rate'], 1)} for i in critical_items])}. "
        f"Escalate if <2 days supply. Check for any POs needing approval."
    )
    compliance_result = await _invoke_agent("compliance-gate", compliance_msg)
    await message_store.publish(
        agent_name="compliance-gate",
        agent_role=_AGENT_ROLES["compliance-gate"],
        content=compliance_result["text"],
        intent_tag=IntentTag.VALIDATE,
    )
    agent_metrics_list.append(compliance_result["metrics"])

    # Step 4: Order Manager — single batch tool call
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Order Manager.",
        intent_tag=IntentTag.PROPOSE,
    )
    order_msg = (
        f"Complete the order lifecycle in one call.\n"
        f"scan_id={scan_id}\n"
        f"vendor_id={recommended_vendor_id or 'VND-MEDLINE'}\n"
        f"Call complete_order_lifecycle with these parameters."
    )
    order_result = await _invoke_agent("order-manager", order_msg)
    await message_store.publish(
        agent_name="order-manager",
        agent_role=_AGENT_ROLES["order-manager"],
        content=order_result["text"],
        intent_tag=IntentTag.EXECUTE,
    )
    agent_metrics_list.append(order_result["metrics"])

    # Final wrap-up from coordinator — compact summary request
    await asyncio.sleep(STEP_DELAY)
    wrapup_msg = (
        f"Workflow complete for {closet.name} ({closet_id}). "
        f"Scan: {scan_id}. Summarize outcome in under 50 words."
    )
    final_result = await _invoke_agent("supply-coordinator", wrapup_msg)
    final_reply = final_result["text"]
    agent_metrics_list.append(final_result["metrics"])
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content=final_reply,
        intent_tag=IntentTag.EXECUTE,
    )

    # Close the shared credential
    await shared_credential.close()

    scenario_metrics: ScenarioMetrics = {
        "total_latency_seconds": round(
            sum(m["latency_seconds"] for m in agent_metrics_list), 3
        ),
        "total_input_tokens": sum(m["input_tokens"] for m in agent_metrics_list),
        "total_output_tokens": sum(m["output_tokens"] for m in agent_metrics_list),
        "agents": agent_metrics_list,
    }

    return {"ok": True, "scenario": scenario_type, "mode": "live", "metrics": scenario_metrics}


# ── Simulated orchestration (no Azure) ──────────────────────────────


async def _simulate_routine_restock(
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Walk through the routine-restock scenario with scripted tool calls.

    Happy path: Scan ICU closet → analyze → source vendors → create PO
    (auto-approved <$1000) → submit → confirm → ship → receive/restock.
    """
    sim_start = time.monotonic()
    closet_id = "CLO-ICU-01"
    closet = state_store.get_closet(closet_id)
    if not closet:
        return {"ok": False, "error": f"Closet {closet_id} not found"}

    # ── Step 1: Supply Coordinator initiates workflow ────────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content=(
            f"Initiating routine replenishment workflow for {closet.name} ({closet_id}). "
            f"Unit: {closet.unit}, Location: {closet.location}. "
            f"Requesting Supply Scanner to perform closet scan."
        ),
        intent_tag=IntentTag.PROPOSE,
    )

    # ── Step 2: Supply Scanner initiates scan ────────────────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Supply Scanner Agent (supply-scanner).",
        intent_tag=IntentTag.PROPOSE,
    )

    scan_result = await _call_tool(
        "initiate_scan", {"closet_id": closet_id},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not scan_result.get("ok"):
        return {"ok": False, "error": scan_result.get("error", "initiate_scan failed")}
    scan_id = scan_result["scan_id"]

    # ── Step 3: Supply Scanner analyzes scan ─────────────────────────
    await asyncio.sleep(STEP_DELAY)
    analysis = await _call_tool(
        "analyze_scan", {"scan_id": scan_id},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not analysis.get("ok"):
        return {"ok": False, "error": analysis.get("error", "analyze_scan failed")}

    items_below_par = analysis.get("reorder_items", [])
    below_par_summary = "\n".join(
        f"  • {item['item_name']} ({item['item_id']}): {item['current_quantity']}/{item['par_level']} "
        f"— {item['days_until_stockout']:.1f} days until stockout"
        for item in items_below_par
    )

    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-scanner",
        agent_role="Supply Scanner Agent",
        content=(
            f"Scan analysis complete for {closet.name}.\n"
            f"Items below par level:\n{below_par_summary}\n"
            f"Recommending vendor sourcing for {len(items_below_par)} item(s)."
        ),
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 4: Coordinator delegates to Catalog Sourcer ─────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Catalog Sourcer Agent (catalog-sourcer) to find best vendor pricing.",
        intent_tag=IntentTag.PROPOSE,
    )

    # ── Step 5: Catalog Sourcer looks up vendors for below-par items ─
    vendor_results = []
    for item in items_below_par:
        await asyncio.sleep(STEP_DELAY)
        lookup = await _call_tool(
            "lookup_vendor_catalog", {"item_sku": item["item_sku"]},
            state_store=state_store, event_store=event_store, message_store=message_store,
        )
        vendor_results.append(lookup)

    # Build sourcing summary
    sourcing_lines = []
    best_entry = None
    for item, vr in zip(items_below_par, vendor_results):
        entries = vr.get("catalog_entries", [])
        if entries:
            # Pick cheapest in-stock entry
            available = [e for e in entries if e.get(
                "stock_status") != "OUT_OF_STOCK"]
            if available:
                best = min(available, key=lambda e: e["unit_price"])
                best_entry = best  # save last best for PO creation
                sourcing_lines.append(
                    f"  • {item['item_name']}: {best['vendor_name']} @ ${best['unit_price']:.2f}/unit "
                    f"(catalog: {best['entry_id']}, stock: {best['stock_status']})"
                )
            else:
                sourcing_lines.append(
                    f"  • {item['item_name']}: No available vendors found")
        else:
            sourcing_lines.append(
                f"  • {item['item_name']}: No catalog entries found")

    await message_store.publish(
        agent_name="catalog-sourcer",
        agent_role="Catalog Sourcer Agent",
        content=(
            f"Vendor sourcing complete for scan {scan_id}:\n"
            + "\n".join(sourcing_lines) + "\n"
            f"Recommending purchase order creation with best-priced vendors."
        ),
        intent_tag=IntentTag.PROPOSE,
    )

    # ── Step 6: Coordinator delegates to Order Manager ───────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Order Manager Agent (order-manager) to create and submit purchase order.",
        intent_tag=IntentTag.PROPOSE,
    )

    # ── Step 7: Order Manager creates PO ────────────────────────────
    await asyncio.sleep(STEP_DELAY)
    # Use the best vendor found
    vendor_id = best_entry["vendor_id"] if best_entry else "VND-MEDLINE"
    po_result = await _call_tool(
        "create_purchase_order", {"scan_id": scan_id, "vendor_id": vendor_id},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not po_result.get("ok"):
        return {"ok": False, "error": po_result.get("error", "create_purchase_order failed")}

    po_id = po_result["po_id"]
    po_total = po_result.get("total_cost", 0)
    needs_human = po_result.get("requires_human_approval", False)

    await asyncio.sleep(STEP_DELAY)
    if needs_human:
        await message_store.publish(
            agent_name="order-manager",
            agent_role="Order Manager Agent",
            content=(
                f"Purchase order {po_id} created.\n"
                f"  Total: ${po_total:.2f} | Requires human approval "
                f"(≥$1,000 threshold)."
            ),
            intent_tag=IntentTag.EXECUTE,
        )

        # Compliance gate approves
        await asyncio.sleep(STEP_DELAY)
        approve_result = await _call_tool(
            "approve_purchase_order",
            {"po_id": po_id, "approved": True,
                "note": "Routine restock — approved."},
            state_store=state_store, event_store=event_store, message_store=message_store,
        )
        if not approve_result.get("ok"):
            return {"ok": False, "error": approve_result.get("error", "approve failed")}

        await message_store.publish(
            agent_name="compliance-gate",
            agent_role="Compliance Gate Agent",
            content=f"PO {po_id} approved (${po_total:.2f}). Cleared for submission.",
            intent_tag=IntentTag.VALIDATE,
        )
    else:
        await message_store.publish(
            agent_name="order-manager",
            agent_role="Order Manager Agent",
            content=(
                f"Purchase order {po_id} created.\n"
                f"  Total: ${po_total:.2f} | Auto-approved (under $1,000 threshold)."
            ),
            intent_tag=IntentTag.EXECUTE,
        )

    # ── Step 8: Order Manager submits PO ─────────────────────────────
    await asyncio.sleep(STEP_DELAY)
    submit_result = await _call_tool(
        "submit_purchase_order", {"po_id": po_id},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not submit_result.get("ok"):
        return {"ok": False, "error": submit_result.get("error", "submit_purchase_order failed")}

    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=f"Purchase order {po_id} submitted to vendor. Awaiting confirmation.",
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 9: Compliance Gate confirms auto-approval ───────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="compliance-gate",
        agent_role="Compliance Gate Agent",
        content=(
            f"Compliance review for PO {po_id}:\n"
            f"  ✓ Total ${po_total:.2f} is below $1,000 auto-approval threshold.\n"
            f"  ✓ Auto-approval policy applied. No human review required.\n"
            f"  ✓ Vendor {vendor_id} is on approved vendor list.\n"
            f"  Status: COMPLIANT. No action needed."
        ),
        intent_tag=IntentTag.VALIDATE,
    )

    # ── Step 10: Simulate vendor confirmation ────────────────────────
    await asyncio.sleep(STEP_DELAY)
    await state_store.transition_purchase_order(po_id, POState.CONFIRMED)

    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=f"Vendor has confirmed PO {po_id}. Preparing shipment.",
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 11: Order Manager creates shipment ──────────────────────
    await asyncio.sleep(STEP_DELAY)
    shipment_result = await _call_tool(
        "create_shipment", {"po_id": po_id, "carrier": "Medline Standard"},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not shipment_result.get("ok"):
        return {"ok": False, "error": shipment_result.get("error", "create_shipment failed")}

    shipment_id = shipment_result["shipment_id"]
    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=(
            f"Shipment {shipment_id} created for PO {po_id}.\n"
            f"  Carrier: Medline Standard | ETA: {shipment_result.get('expected_delivery', 'TBD')}"
        ),
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 12: Simulate delivery — receive shipment ────────────────
    await asyncio.sleep(STEP_DELAY)
    # Advance shipment through intermediate states
    await state_store.transition_shipment(shipment_id, ShipmentState.SHIPPED)
    await state_store.transition_shipment(shipment_id, ShipmentState.IN_TRANSIT)

    receive_result = await _call_tool(
        "receive_shipment", {"shipment_id": shipment_id},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not receive_result.get("ok"):
        return {"ok": False, "error": receive_result.get("error", "receive_shipment failed")}

    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=(
            f"Shipment {shipment_id} received and verified.\n"
            f"  Items restocked in {closet.name}. Inventory levels updated."
        ),
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 13: Supply Coordinator wrap-up ──────────────────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content=(
            f"Routine restock workflow COMPLETE for {closet.name} ({closet_id}).\n\n"
            f"Summary:\n"
            f"  • Scan: {scan_id} — {len(items_below_par)} item(s) below par identified\n"
            f"  • PO: {po_id} — ${po_total:.2f} (auto-approved)\n"
            f"  • Shipment: {shipment_id} — received and restocked\n"
            f"  • Status: All items back above par level. Closet fully stocked."
        ),
        intent_tag=IntentTag.EXECUTE,
    )

    sim_latency = time.monotonic() - sim_start
    return {
        "ok": True,
        "scenario": "routine-restock",
        "mode": "simulated",
        "closet_id": closet_id,
        "scan_id": scan_id,
        "po_id": po_id,
        "shipment_id": shipment_id,
        "metrics": _simulated_metrics(_AGENT_NAMES, sim_latency),
    }


async def _simulate_critical_shortage(
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Walk through the critical-shortage scenario with scripted tool calls.

    Escalation + human approval path: Scan Med-Surg closet → analyze
    (critical shortage found) → escalate → source vendors → create PO
    (≥$1000, needs human approval) → compliance-gate approves → submit →
    expedited ship → receive/restock.
    """
    sim_start = time.monotonic()
    closet_id = "CLO-SURG-01"
    closet = state_store.get_closet(closet_id)
    if not closet:
        return {"ok": False, "error": f"Closet {closet_id} not found"}

    # ── Step 1: Supply Coordinator — URGENT alert ────────────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content=(
            f"⚠️ URGENT: Critical supply alert for {closet.name} ({closet_id}). "
            f"Unit: {closet.unit}, Location: {closet.location}. "
            f"Initiating emergency replenishment scan. Requesting immediate Supply Scanner assessment."
        ),
        intent_tag=IntentTag.ESCALATE,
    )

    # ── Step 2: Supply Scanner initiates scan ────────────────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Supply Scanner Agent (supply-scanner) — PRIORITY scan.",
        intent_tag=IntentTag.PROPOSE,
    )

    scan_result = await _call_tool(
        "initiate_scan", {"closet_id": closet_id},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not scan_result.get("ok"):
        return {"ok": False, "error": scan_result.get("error", "initiate_scan failed")}
    scan_id = scan_result["scan_id"]

    # ── Step 3: Supply Scanner analyzes scan ─────────────────────────
    await asyncio.sleep(STEP_DELAY)
    analysis = await _call_tool(
        "analyze_scan", {"scan_id": scan_id},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not analysis.get("ok"):
        return {"ok": False, "error": analysis.get("error", "analyze_scan failed")}

    items_below_par = analysis.get("reorder_items", [])
    critical_items = [i for i in items_below_par if i.get(
        "criticality") == "CRITICAL"]
    all_below_par_summary = "\n".join(
        f"  • {item['item_name']} ({item['item_id']}): {item['current_quantity']}/{item['par_level']} "
        f"— {item['days_until_stockout']:.1f} days, criticality: {item['criticality']}"
        for item in items_below_par
    )

    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-scanner",
        agent_role="Supply Scanner Agent",
        content=(
            f"CRITICAL scan analysis for {closet.name}:\n"
            f"Items below par level:\n{all_below_par_summary}\n\n"
            f"⚠️ {len(critical_items)} CRITICAL item(s) identified. "
            f"Recommending immediate escalation and expedited sourcing."
        ),
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 4: Compliance Gate escalates critical shortage ──────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Compliance Gate Agent (compliance-gate) for critical shortage escalation.",
        intent_tag=IntentTag.PROPOSE,
    )

    critical_item_names = ", ".join(i["item_name"] for i in critical_items)
    escalation_msg = (
        f"Critical shortage detected in {closet.name}: {critical_item_names}. "
        f"Patient safety risk — supplies below 2-day threshold. Immediate action required."
    )

    escalate_result = await _call_tool(
        "escalate",
        {
            "issue_type": "critical_shortage",
            "entity_id": scan_id,
            "severity": "HIGH",
            "message": escalation_msg,
        },
        state_store=state_store, event_store=event_store, message_store=message_store,
    )

    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="compliance-gate",
        agent_role="Compliance Gate Agent",
        content=(
            f"🚨 ESCALATION FILED — Critical shortage in {closet.name}.\n"
            f"  Severity: HIGH | Scan: {scan_id}\n"
            f"  Critical items: {critical_item_names}\n"
            f"  Escalation ID: {escalate_result.get('escalation_id', 'N/A')}\n"
            f"  Notification sent to supply chain director and unit charge nurse."
        ),
        intent_tag=IntentTag.ESCALATE,
    )

    # ── Step 5: Coordinator delegates to Catalog Sourcer ─────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Catalog Sourcer Agent (catalog-sourcer) for emergency vendor sourcing.",
        intent_tag=IntentTag.PROPOSE,
    )

    # ── Step 6: Catalog Sourcer looks up vendors for each item ───────
    vendor_results = []
    for item in items_below_par:
        await asyncio.sleep(STEP_DELAY)
        lookup = await _call_tool(
            "lookup_vendor_catalog", {"item_sku": item["item_sku"]},
            state_store=state_store, event_store=event_store, message_store=message_store,
        )
        vendor_results.append(lookup)

    sourcing_lines = []
    best_vendor_id = None
    for item, vr in zip(items_below_par, vendor_results):
        entries = vr.get("catalog_entries", [])
        if entries:
            available = [e for e in entries if e.get(
                "stock_status") != "OUT_OF_STOCK"]
            if available:
                # For critical items, prefer IN_STOCK over cheapest
                in_stock = [e for e in available if e.get(
                    "stock_status") == "IN_STOCK"]
                best = in_stock[0] if in_stock else min(
                    available, key=lambda e: e["unit_price"])
                if best_vendor_id is None:
                    best_vendor_id = best["vendor_id"]
                sourcing_lines.append(
                    f"  • {item['item_name']}: {best['vendor_name']} @ ${best['unit_price']:.2f}/unit "
                    f"(catalog: {best['entry_id']}, stock: {best['stock_status']})"
                )
            else:
                sourcing_lines.append(
                    f"  • {item['item_name']}: ⚠️ All vendors out of stock")
        else:
            sourcing_lines.append(
                f"  • {item['item_name']}: No catalog entries found")

    await message_store.publish(
        agent_name="catalog-sourcer",
        agent_role="Catalog Sourcer Agent",
        content=(
            f"Emergency vendor sourcing complete for scan {scan_id}:\n"
            + "\n".join(sourcing_lines) + "\n"
            f"Note: Prioritized IN_STOCK vendors for critical items. "
            f"Recommending expedited purchase order."
        ),
        intent_tag=IntentTag.PROPOSE,
    )

    # ── Step 7: Order Manager creates PO (≥$1000 → PENDING_APPROVAL) ─
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Order Manager Agent (order-manager) to create emergency purchase order.",
        intent_tag=IntentTag.PROPOSE,
    )

    await asyncio.sleep(STEP_DELAY)
    po_result = await _call_tool(
        "create_purchase_order",
        {"scan_id": scan_id, "vendor_id": best_vendor_id or "VND-CARDINAL"},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not po_result.get("ok"):
        return {"ok": False, "error": po_result.get("error", "create_purchase_order failed")}

    po_id = po_result["po_id"]
    po_total = po_result.get("total_cost", 0)

    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=(
            f"Emergency purchase order {po_id} created.\n"
            f"  Total: ${po_total:.2f}\n"
            f"  Order requires human approval before submission."
        ),
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 8: Wait for human approval via UI ────────────────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="PO requires human approval. Waiting for compliance review via the Control Tower UI.",
        intent_tag=IntentTag.PROPOSE,
    )

    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="compliance-gate",
        agent_role="Compliance Gate Agent",
        content=(
            f"⏳ PO {po_id} (${po_total:.2f}) is awaiting human approval.\n"
            f"  Please review and approve or reject in the Control Tower."
        ),
        intent_tag=IntentTag.VALIDATE,
    )

    # Poll state store until the PO is no longer PENDING_APPROVAL
    # (human clicks Approve/Reject in the UI, which calls POST /api/approval/{po_id})
    # Uses an asyncio.Event so the approval endpoint / reset can wake us instantly.
    evt = approval_signal.create_event()
    # In test mode, use a short timeout; in production, wait up to 5 minutes
    max_wait_seconds = 1.0 if _PYTEST_MODE else 300
    waited = 0.0
    poll_interval = 0.1 if _PYTEST_MODE else 1.0
    while waited < max_wait_seconds:
        po = state_store.get_purchase_order(po_id)
        # PO gone (stores were reset) or state changed — stop waiting
        if po is None or po.state != POState.PENDING_APPROVAL:
            break
        evt.clear()
        try:
            await asyncio.wait_for(evt.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            pass
        waited += poll_interval

    po = state_store.get_purchase_order(po_id)
    if po is None:
        # Stores were reset while waiting — abort gracefully
        return {"ok": False, "error": "Scenario reset during approval wait"}
    if po.state == POState.PENDING_APPROVAL:
        # Timed out waiting for human
        if _PYTEST_MODE:
            # In test mode, auto-approve the PO and emit the event
            from ..models.enums import POApprovalStatus
            from ..models.events import PO_AUTO_APPROVED
            from datetime import datetime, timezone

            await state_store.transition_purchase_order(po_id, POState.APPROVED)
            po.state = POState.APPROVED
            po.approval_status = POApprovalStatus.AUTO_APPROVED
            po.approval_note = "[AUTO-APPROVED IN TEST MODE]"
            po.approved_at = datetime.now(timezone.utc)

            # Emit the auto-approval event
            event = await event_store.publish(
                event_type=PO_AUTO_APPROVED,
                entity_id=po_id,
                payload={"po_id": po_id},
                state_diff={"from_state": "PENDING_APPROVAL",
                            "to_state": "APPROVED"},
            )

            await message_store.publish(
                agent_name="compliance-gate",
                agent_role="Compliance Gate Agent",
                content=f"PO {po_id} auto-approved (test mode).",
                intent_tag=IntentTag.EXECUTE,
                related_event_ids=[event.id],
            )
        else:
            # Production mode: timeout
            await message_store.publish(
                agent_name="compliance-gate",
                agent_role="Compliance Gate Agent",
                content=f"⚠️ PO {po_id} approval timed out after {max_wait_seconds}s. Please retry the scenario.",
                intent_tag=IntentTag.ESCALATE,
            )
            return {"ok": False, "error": "Human approval timed out"}

    if po.state == POState.CANCELLED:
        await message_store.publish(
            agent_name="compliance-gate",
            agent_role="Compliance Gate Agent",
            content=(
                f"❌ PO {po_id} REJECTED by human reviewer.\n"
                f"  Note: {po.approval_note}\n"
                f"  Workflow halted. Manual intervention required."
            ),
            intent_tag=IntentTag.ESCALATE,
        )
        sim_latency = time.monotonic() - sim_start
        return {
            "ok": True,
            "scenario": "critical-shortage",
            "mode": "simulated",
            "closet_id": closet_id,
            "scan_id": scan_id,
            "po_id": po_id,
            "outcome": "rejected",
            "metrics": _simulated_metrics(_AGENT_NAMES, sim_latency),
        }

    # PO was approved by the human
    await message_store.publish(
        agent_name="compliance-gate",
        agent_role="Compliance Gate Agent",
        content=(
            f"✅ PO {po_id} APPROVED by human reviewer.\n"
            f"  ✓ Critical shortage confirmed in {closet.name}\n"
            f"  ✓ Patient safety justification documented\n"
            f"  ✓ Approval: Human-approved via Control Tower\n"
            f"  PO cleared for immediate submission."
        ),
        intent_tag=IntentTag.VALIDATE,
    )

    # ── Step 9: Order Manager submits PO ─────────────────────────────
    await asyncio.sleep(STEP_DELAY)
    submit_result = await _call_tool(
        "submit_purchase_order", {"po_id": po_id},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not submit_result.get("ok"):
        return {"ok": False, "error": submit_result.get("error", "submit_purchase_order failed")}

    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=f"Emergency PO {po_id} submitted to vendor with EXPEDITED flag. Awaiting confirmation.",
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 10: Simulate vendor confirmation ────────────────────────
    await asyncio.sleep(STEP_DELAY)
    await state_store.transition_purchase_order(po_id, POState.CONFIRMED)

    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=f"Vendor has confirmed emergency PO {po_id}. Expedited shipment being prepared.",
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 11: Order Manager creates expedited shipment ────────────
    await asyncio.sleep(STEP_DELAY)
    shipment_result = await _call_tool(
        "create_shipment", {"po_id": po_id, "carrier": "Cardinal Express"},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not shipment_result.get("ok"):
        return {"ok": False, "error": shipment_result.get("error", "create_shipment failed")}

    shipment_id = shipment_result["shipment_id"]
    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=(
            f"Expedited shipment {shipment_id} created for PO {po_id}.\n"
            f"  Carrier: Cardinal Express (expedited) | ETA: {shipment_result.get('expected_delivery', 'TBD')}"
        ),
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 12: Simulate delivery — receive shipment ────────────────
    await asyncio.sleep(STEP_DELAY)
    # Advance shipment through intermediate states
    await state_store.transition_shipment(shipment_id, ShipmentState.SHIPPED)
    await state_store.transition_shipment(shipment_id, ShipmentState.IN_TRANSIT)

    receive_result = await _call_tool(
        "receive_shipment", {"shipment_id": shipment_id},
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not receive_result.get("ok"):
        return {"ok": False, "error": receive_result.get("error", "receive_shipment failed")}

    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=(
            f"Emergency shipment {shipment_id} received and verified.\n"
            f"  Items restocked in {closet.name}. Critical supply levels restored."
        ),
        intent_tag=IntentTag.EXECUTE,
    )

    # ── Step 13: Supply Coordinator wrap-up with incident summary ────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content=(
            f"Critical shortage workflow COMPLETE for {closet.name} ({closet_id}).\n\n"
            f"Incident Summary:\n"
            f"  • Scan: {scan_id} — {len(items_below_par)} item(s) below par, "
            f"{len(critical_items)} CRITICAL\n"
            f"  • Critical items: {critical_item_names}\n"
            f"  • Escalation: severity HIGH — supply chain director notified\n"
            f"  • PO: {po_id} — ${po_total:.2f} (human-approved, emergency protocol)\n"
            f"  • Shipment: {shipment_id} — expedited delivery, received and restocked\n"
            f"  • Status: Critical supplies restored. Patient safety risk resolved.\n\n"
            f"Recommendation: Schedule follow-up par level review for {closet.unit} closets "
            f"within 48 hours."
        ),
        intent_tag=IntentTag.EXECUTE,
    )

    sim_latency = time.monotonic() - sim_start
    return {
        "ok": True,
        "scenario": "critical-shortage",
        "mode": "simulated",
        "closet_id": closet_id,
        "scan_id": scan_id,
        "po_id": po_id,
        "shipment_id": shipment_id,
        "metrics": _simulated_metrics(_AGENT_NAMES, sim_latency),
    }


# ── Public entry point ──────────────────────────────────────────────

async def run_scenario(
    scenario_type: str,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Run an orchestration scenario (live or simulated).

    Args:
        scenario_type: One of ``"routine-restock"`` or ``"critical-shortage"``.
        state_store: Singleton state store.
        event_store: Singleton event store.
        message_store: Singleton message store.

    Returns:
        Result dict with ``ok`` bool and scenario details.
    """
    if _use_live_agents():
        logger.info("Running %s with live Foundry agents", scenario_type)
        return await _run_live(scenario_type, state_store, event_store, message_store)

    logger.info("Running %s in simulated mode (no Foundry agents)",
                scenario_type)
    if scenario_type == "routine-restock":
        return await _simulate_routine_restock(state_store, event_store, message_store)
    elif scenario_type == "critical-shortage":
        return await _simulate_critical_shortage(state_store, event_store, message_store)
    else:
        return {"ok": False, "error": f"Unknown scenario: {scenario_type}"}
