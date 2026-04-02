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
import time
from pathlib import Path
from typing import Any, TypedDict

from ..config import settings
from ..events.event_store import EventStore
from ..messages.message_store import MessageStore
from ..models.enums import IntentTag, POState, ScanState, ShipmentState
from ..state.store import StateStore
from ..tools import tool_functions

logger = logging.getLogger(__name__)


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
    "create_purchase_order": tool_functions.create_purchase_order,
    "approve_purchase_order": tool_functions.approve_purchase_order,
    "submit_purchase_order": tool_functions.submit_purchase_order,
    "create_shipment": tool_functions.create_shipment,
    "receive_shipment": tool_functions.receive_shipment,
    "publish_event": tool_functions.publish_event,
    "escalate": tool_functions.escalate,
}


# ── Agent prompt loader (ADR-008) ───────────────────────────────────

_PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt(agent_name: str) -> str:
    path = _PROMPT_DIR / f"{agent_name}.txt"
    return path.read_text(encoding="utf-8")


# ── Helpers ─────────────────────────────────────────────────────────

STEP_DELAY = 0.35  # seconds between simulated steps for realistic SSE pacing


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
    return bool(settings.PROJECT_ENDPOINT or settings.PROJECT_CONNECTION_STRING)


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
    """Run orchestration using the Responses API with per-agent instructions.

    Each agent is defined by its system prompt and tool set.  All calls use
    the same model deployment (e.g. ``gpt-4.1``) with the ``instructions``
    and ``tools`` parameters customised per agent.
    """
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage

    from ..tools.tool_schemas import AGENT_TOOLS

    credential = DefaultAzureCredential()
    if settings.PROJECT_ENDPOINT:
        project_client = AIProjectClient(
            endpoint=settings.PROJECT_ENDPOINT,
            credential=credential,
        )
    else:
        parts = settings.PROJECT_CONNECTION_STRING.split(";")
        host, sub_id, rg, project = parts
        endpoint = f"https://{host}/api/projects/{project}"
        project_client = AIProjectClient(
            endpoint=endpoint, credential=credential)

    openai_client = project_client.get_openai_client()

    # Read effective config from runtime config store (falls back to env vars)
    from ..config_store import runtime_config

    effective = runtime_config.get_config()
    default_deployment = effective["model_deployment"]
    _model_overrides: dict[str, str] = effective["agent_model_overrides"]
    _token_overrides: dict[str, int] = effective["agent_max_tokens_overrides"]
    default_max_tokens: int = effective["max_output_tokens"]

    async def _invoke_agent(agent_name: str, user_message: str) -> dict:
        """Invoke an agent via the Responses API with its prompt and tools.

        Returns a dict with ``text`` (the agent's reply) and ``metrics``.
        """
        import openai as _openai_mod

        start = time.monotonic()
        total_input_tokens = 0
        total_output_tokens = 0
        rounds = 0

        deployment = _model_overrides.get(agent_name) or default_deployment
        resolved_max_tokens = _token_overrides.get(
            agent_name) or default_max_tokens

        agent_instructions = _load_prompt(agent_name)
        # Convert Chat Completions tool format to Responses API format
        agent_tools = [
            {"type": "function", **t["function"]}
            for t in AGENT_TOOLS.get(agent_name, [])
        ]

        async def _create_with_retry(**kwargs: Any) -> Any:
            """Call responses.create with exponential backoff on 429."""
            max_retries = 5
            base_delay = 2.0
            for attempt in range(max_retries + 1):
                try:
                    return await asyncio.to_thread(
                        openai_client.responses.create, **kwargs
                    )
                except _openai_mod.RateLimitError:
                    if attempt == max_retries:
                        raise
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Rate limited on %s (attempt %d/%d), retrying in %.1fs",
                        agent_name, attempt + 1, max_retries, delay,
                    )
                    await asyncio.sleep(delay)
            raise RuntimeError("unreachable")  # pragma: no cover

        response = await _create_with_retry(
            model=deployment,
            instructions=agent_instructions,
            input=user_message,
            tools=agent_tools,
            max_output_tokens=resolved_max_tokens,
        )
        rounds = 1
        if getattr(response, "usage", None):
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

        # Handle truncation on initial response
        if getattr(response, "status", None) == "incomplete":
            logger.warning(
                "agent=%s response truncated at %d max_output_tokens on initial call",
                agent_name, resolved_max_tokens,
            )

        max_rounds = 15
        for _ in range(max_rounds):
            # Collect any tool calls from the response output
            tool_calls = [
                item for item in response.output
                if isinstance(item, ResponseFunctionToolCall)
            ]
            if not tool_calls:
                break  # No tool calls → agent is done

            # Execute each tool call locally and build result items
            tool_results: list[dict] = []
            for tc in tool_calls:
                fn_args = json.loads(tc.arguments)
                result = await _call_tool(
                    tc.name,
                    fn_args,
                    state_store=state_store,
                    event_store=event_store,
                    message_store=message_store,
                )
                tool_results.append({
                    "type": "function_call_output",
                    "call_id": tc.call_id,
                    "output": json.dumps(result),
                })

            # Send tool results back to the agent
            response = await _create_with_retry(
                model=deployment,
                instructions=agent_instructions,
                input=tool_results,
                tools=agent_tools,
                previous_response_id=response.id,
                max_output_tokens=resolved_max_tokens,
            )
            rounds += 1
            if getattr(response, "usage", None):
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

            # Handle truncation — log warning and break out with what we have
            if getattr(response, "status", None) == "incomplete":
                logger.warning(
                    "agent=%s response truncated at %d max_output_tokens (round %d)",
                    agent_name, resolved_max_tokens, rounds,
                )
                break

        # Extract the final text from output items
        text_parts: list[str] = []
        for item in response.output:
            if isinstance(item, ResponseOutputMessage):
                for content in item.content:
                    if hasattr(content, "text"):
                        text_parts.append(content.text)
        text = " ".join(text_parts) if text_parts else ""

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

    state_snapshot = json.dumps(
        {
            "closet": closet.model_dump(mode="json"),
            "items": [i.model_dump(mode="json") for i in closet_items],
            "scans": [
                s.model_dump(mode="json")
                for s in state_store.get_scans()
            ],
        },
        indent=2,
    )

    initial_msg = (
        f"Supply closet {closet.name} ({closet_id}) needs replenishment assessment. "
        f"Scenario type: {scenario_type}.\n\n"
        f"Current state:\n{state_snapshot}\n\n"
        f"Coordinate the full replenishment workflow. For each step, describe "
        f"what you are doing and use the tools available to you. "
        f"After your initial assessment, I will invoke the specialist agents "
        f"(supply-scanner, catalog-sourcer, compliance-gate, order-manager) "
        f"on your behalf. Tell me which agent to invoke next and what to ask them."
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

    # Step 2: Invoke specialist agents in sequence
    specialist_sequence = [
        ("supply-scanner", IntentTag.EXECUTE),
        ("catalog-sourcer", IntentTag.PROPOSE),
        ("compliance-gate", IntentTag.VALIDATE),
        ("order-manager", IntentTag.EXECUTE),
    ]

    context = (
        f"Closet: {closet.name} ({closet_id}), "
        f"Unit: {closet.unit}, Floor: {closet.floor}. "
        f"Scenario: {scenario_type}."
    )

    for agent_name, intent_tag in specialist_sequence:
        role = _AGENT_ROLES[agent_name]
        await asyncio.sleep(STEP_DELAY)

        # Announce delegation
        await message_store.publish(
            agent_name="supply-coordinator",
            agent_role="Supply Coordinator",
            content=f"Delegating to {role} ({agent_name}).",
            intent_tag=IntentTag.PROPOSE,
        )

        specialist_msg = (
            f"{context}\n\n"
            f"Supply Coordinator says: {coordinator_reply}\n\n"
            f"Execute your role. Use your tools to take action."
        )

        specialist_result = await _invoke_agent(agent_name, specialist_msg)
        reply = specialist_result["text"]
        agent_metrics_list.append(specialist_result["metrics"])
        await message_store.publish(
            agent_name=agent_name,
            agent_role=role,
            content=reply,
            intent_tag=intent_tag,
        )

        # Feed specialist reply back for context
        context += f"\n\n{role} responded: {reply}"

    # Final wrap-up from coordinator
    await asyncio.sleep(STEP_DELAY)
    wrapup_msg = (
        f"All specialist agents have completed their work.\n\n{context}\n\n"
        f"Summarize the outcome of this replenishment workflow."
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

    # ── Step 8: Compliance Gate approves PO ──────────────────────────
    await asyncio.sleep(STEP_DELAY)
    await message_store.publish(
        agent_name="supply-coordinator",
        agent_role="Supply Coordinator",
        content="Delegating to Compliance Gate Agent (compliance-gate) for emergency PO approval.",
        intent_tag=IntentTag.PROPOSE,
    )

    await asyncio.sleep(STEP_DELAY)
    approve_result = await _call_tool(
        "approve_purchase_order",
        {
            "po_id": po_id,
            "approved": True,
            "note": (
                "Emergency approval granted — critical shortage in Med-Surg closet. "
                "Patient safety risk. Expedited processing authorized."
            ),
        },
        state_store=state_store, event_store=event_store, message_store=message_store,
    )
    if not approve_result.get("ok"):
        return {"ok": False, "error": approve_result.get("error", "approve_purchase_order failed")}

    await message_store.publish(
        agent_name="compliance-gate",
        agent_role="Compliance Gate Agent",
        content=(
            f"PO {po_id} APPROVED — emergency authorization.\n"
            f"  ✓ Critical shortage confirmed in {closet.name}\n"
            f"  ✓ Patient safety justification documented\n"
            f"  ✓ Approval: Human-approved (emergency protocol)\n"
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
