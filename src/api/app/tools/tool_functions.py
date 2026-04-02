"""Deterministic tool functions — the ONLY way agents change state (ADR-003).

Each function takes the three stores as arguments, validates inputs,
mutates state via the StateStore transition helpers, emits events, and
publishes agent messages. Returns a structured dict result.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..events.event_store import EventStore
from ..messages.message_store import MessageStore
from ..models.entities import (
    CatalogEntry,
    POLineItem,
    PurchaseOrder,
    ReorderItem,
    ScanResult,
    Shipment,
)
from ..models.enums import (
    ContractTier,
    IntentTag,
    ItemCriticality,
    POApprovalStatus,
    POState,
    ScanState,
    ShipmentState,
    VendorStockStatus,
)
from ..models.events import (
    CLOSET_RESTOCKED,
    CLOSET_SCAN_ANALYZED,
    CLOSET_SCAN_INITIATED,
    CRITICAL_SHORTAGE_DETECTED,
    ITEMS_BELOW_PAR_IDENTIFIED,
    PO_AUTO_APPROVED,
    PO_CREATED,
    PO_HUMAN_APPROVED,
    PO_HUMAN_REJECTED,
    PO_PENDING_HUMAN_APPROVAL,
    PO_SUBMITTED,
    SHIPMENT_CREATED,
    SHIPMENT_DELIVERED,
    VENDOR_LOOKUP_COMPLETED,
)
from ..state.store import StateStore

# Auto-approval threshold (DOMAIN-C-002)
PO_AUTO_APPROVAL_THRESHOLD = 1000.0


# ── Read-only tools ─────────────────────────────────────────────────

async def get_scan(
    scan_id: str,
    *,
    state_store: StateStore,
    **_kwargs,
) -> dict:
    """Look up a single scan result by ID."""
    scan = state_store.get_scan(scan_id)
    if scan is None:
        return {"ok": False, "error": f"Scan {scan_id} not found"}
    return {"ok": True, "scan": scan.model_dump(mode="json")}


async def get_items(
    *,
    state_store: StateStore,
    closet_id: Optional[str] = None,
    category: Optional[str] = None,
    criticality: Optional[str] = None,
    **_kwargs,
) -> dict:
    """List supply items, optionally filtered by closet, category, and/or criticality."""

    def _filter(i):
        if closet_id and i.closet_id != closet_id:
            return False
        if category and i.category != category:
            return False
        if criticality and i.criticality != criticality:
            return False
        return True

    items = state_store.get_items(filter_fn=_filter)
    return {"ok": True, "items": [i.model_dump(mode="json") for i in items]}


async def get_vendors(
    *,
    state_store: StateStore,
    contract_tier: Optional[str] = None,
    **_kwargs,
) -> dict:
    """List vendors, optionally filtered by contract tier."""

    def _filter(v):
        if contract_tier and v.contract_tier != contract_tier:
            return False
        return True

    vendors = state_store.get_vendors(filter_fn=_filter)
    return {"ok": True, "vendors": [v.model_dump(mode="json") for v in vendors]}


async def get_purchase_orders(
    *,
    state_store: StateStore,
    po_state: Optional[str] = None,
    **_kwargs,
) -> dict:
    """List purchase orders, optionally filtered by state."""

    def _filter(po):
        if po_state and po.state != po_state:
            return False
        return True

    pos = state_store.get_purchase_orders(filter_fn=_filter)
    return {"ok": True, "purchase_orders": [po.model_dump(mode="json") for po in pos]}


async def get_shipments(
    *,
    state_store: StateStore,
    shipment_state: Optional[str] = None,
    **_kwargs,
) -> dict:
    """List shipments, optionally filtered by state."""

    def _filter(s):
        if shipment_state and s.state != shipment_state:
            return False
        return True

    shipments = state_store.get_shipments(filter_fn=_filter)
    return {"ok": True, "shipments": [s.model_dump(mode="json") for s in shipments]}


# ── Scan lifecycle ──────────────────────────────────────────────────

async def initiate_scan(
    closet_id: str,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Initiate a closet scan."""
    closet = state_store.get_closet(closet_id)
    if closet is None:
        return {"ok": False, "error": f"Closet {closet_id} not found"}

    scan_id = f"SCAN-{uuid.uuid4().hex[:8].upper()}"
    scan = ScanResult(id=scan_id, closet_id=closet_id)
    state_store.scans[scan_id] = scan

    event = await event_store.publish(
        event_type=CLOSET_SCAN_INITIATED,
        entity_id=scan_id,
        payload={"scan_id": scan_id, "closet_id": closet_id},
    )

    await message_store.publish(
        agent_name="supply-scanner",
        agent_role="Supply Scanner Agent",
        content=f"Initiated closet scan {scan_id} for {closet.name} ({closet_id}).",
        intent_tag=IntentTag.EXECUTE,
        related_event_ids=[event.id],
    )

    return {"ok": True, "scan_id": scan_id, "closet_id": closet_id}


async def analyze_scan(
    scan_id: str,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Analyze a scan: identify items below par level, compute days-until-stockout."""
    scan = state_store.get_scan(scan_id)
    if scan is None:
        return {"ok": False, "error": f"Scan {scan_id} not found"}

    # Transition INITIATED → ANALYZING
    try:
        await state_store.transition_scan(scan_id, ScanState.ANALYZING)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    # Find items in this closet that are below par
    closet_items = state_store.get_items(
        filter_fn=lambda i: i.closet_id == scan.closet_id
    )

    items_below_par = []
    for item in closet_items:
        if item.current_quantity < item.par_level:
            days_until_stockout = (
                item.current_quantity / item.consumption_rate_per_day
                if item.consumption_rate_per_day > 0
                else float("inf")
            )
            # Find best vendor catalog entry
            catalog_entries = [
                e for e in state_store.catalog.values()
                if e.item_sku == item.sku and e.stock_status == VendorStockStatus.IN_STOCK
            ]
            best_entry = min(catalog_entries, key=lambda e: e.unit_price) if catalog_entries else None

            reorder_item = ReorderItem(
                item_id=item.id,
                item_sku=item.sku,
                item_name=item.name,
                current_quantity=item.current_quantity,
                par_level=item.par_level,
                reorder_quantity=item.reorder_quantity,
                criticality=item.criticality,
                days_until_stockout=round(days_until_stockout, 1),
                recommended_vendor_id=best_entry.vendor_id if best_entry else None,
                recommended_unit_price=best_entry.unit_price if best_entry else None,
            )
            items_below_par.append(reorder_item)

    scan.items_scanned = len(closet_items)
    scan.items_below_par = len(items_below_par)
    scan.items_to_reorder = items_below_par

    # Transition ANALYZING → ITEMS_IDENTIFIED
    await state_store.transition_scan(scan_id, ScanState.ITEMS_IDENTIFIED)

    await event_store.publish(
        event_type=CLOSET_SCAN_ANALYZED,
        entity_id=scan_id,
        payload={"items_scanned": scan.items_scanned},
    )

    event = await event_store.publish(
        event_type=ITEMS_BELOW_PAR_IDENTIFIED,
        entity_id=scan_id,
        payload={
            "items_below_par": scan.items_below_par,
            "reorder_items": [r.model_dump(mode="json") for r in items_below_par],
        },
    )

    await message_store.publish(
        agent_name="supply-scanner",
        agent_role="Supply Scanner Agent",
        content=(
            f"Scan {scan_id} analyzed: {scan.items_scanned} items scanned, "
            f"{scan.items_below_par} below par level."
        ),
        intent_tag=IntentTag.VALIDATE,
        related_event_ids=[event.id],
    )

    return {
        "ok": True,
        "scan_id": scan_id,
        "items_scanned": scan.items_scanned,
        "items_below_par": scan.items_below_par,
        "reorder_items": [r.model_dump(mode="json") for r in items_below_par],
    }


# ── Sourcing ────────────────────────────────────────────────────────

async def lookup_vendor_catalog(
    item_sku: str,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Look up vendor catalog entries for an item SKU."""
    entries = [
        e for e in state_store.catalog.values()
        if e.item_sku == item_sku
    ]
    if not entries:
        return {"ok": False, "error": f"No catalog entries found for SKU {item_sku}"}

    # Rank: in-stock GPO first, then preferred, then spot buy
    tier_rank = {ContractTier.GPO_CONTRACT: 0, ContractTier.PREFERRED: 1, ContractTier.SPOT_BUY: 2}

    in_stock = [e for e in entries if e.stock_status == VendorStockStatus.IN_STOCK]
    recommended = None
    if in_stock:
        recommended = min(in_stock, key=lambda e: (tier_rank.get(e.contract_tier, 9), e.unit_price))

    event = await event_store.publish(
        event_type=VENDOR_LOOKUP_COMPLETED,
        entity_id=item_sku,
        payload={
            "item_sku": item_sku,
            "entries_found": len(entries),
            "recommended_vendor_id": recommended.vendor_id if recommended else None,
        },
    )

    await message_store.publish(
        agent_name="catalog-sourcer",
        agent_role="Catalog Sourcer Agent",
        content=(
            f"Found {len(entries)} catalog entries for SKU {item_sku}. "
            f"Recommended: {recommended.vendor_id if recommended else 'none available'}."
        ),
        intent_tag=IntentTag.PROPOSE,
        related_event_ids=[event.id],
    )

    return {
        "ok": True,
        "item_sku": item_sku,
        "entries": [e.model_dump(mode="json") for e in entries],
        "recommended_vendor_id": recommended.vendor_id if recommended else None,
        "recommended_unit_price": recommended.unit_price if recommended else None,
    }


# ── Purchase order lifecycle ────────────────────────────────────────

async def create_purchase_order(
    scan_id: str,
    vendor_id: str,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Create a PO from a scan's reorder list for a specific vendor.

    POs under $1000 are auto-approved; POs >= $1000 go to PENDING_APPROVAL
    for human review (DOMAIN-C-002 compliance gate rule).
    """
    scan = state_store.get_scan(scan_id)
    if scan is None:
        return {"ok": False, "error": f"Scan {scan_id} not found"}
    vendor = state_store.get_vendor(vendor_id)
    if vendor is None:
        return {"ok": False, "error": f"Vendor {vendor_id} not found"}
    if not scan.items_to_reorder:
        return {"ok": False, "error": f"Scan {scan_id} has no items to reorder"}

    # Build line items from reorder list
    line_items = []
    total_cost = 0.0
    for reorder in scan.items_to_reorder:
        unit_price = reorder.recommended_unit_price or 0.0
        extended = unit_price * reorder.reorder_quantity
        total_cost += extended

        # Look up contract tier from catalog
        catalog_entry = next(
            (e for e in state_store.catalog.values()
             if e.item_sku == reorder.item_sku and e.vendor_id == vendor_id),
            None,
        )
        tier = catalog_entry.contract_tier if catalog_entry else ContractTier.SPOT_BUY

        line_items.append(POLineItem(
            item_sku=reorder.item_sku,
            item_name=reorder.item_name,
            quantity=reorder.reorder_quantity,
            unit_price=unit_price,
            extended_price=extended,
            contract_tier=tier,
            criticality=reorder.criticality,
        ))

    po_id = f"PO-{uuid.uuid4().hex[:8].upper()}"
    requires_human = total_cost >= PO_AUTO_APPROVAL_THRESHOLD

    po = PurchaseOrder(
        id=po_id,
        scan_id=scan_id,
        vendor_id=vendor_id,
        vendor_name=vendor.name,
        line_items=line_items,
        total_cost=round(total_cost, 2),
        requires_human_approval=requires_human,
        closet_id=scan.closet_id,
    )

    if requires_human:
        po.approval_status = POApprovalStatus.PENDING_HUMAN
    else:
        po.approval_status = POApprovalStatus.AUTO_APPROVED
        po.approved_at = datetime.now(timezone.utc)

    state_store.purchase_orders[po_id] = po

    # Transition scan to SOURCING → ORDERING
    try:
        await state_store.transition_scan(scan_id, ScanState.SOURCING)
    except Exception:
        pass  # May already be past this state
    try:
        await state_store.transition_scan(scan_id, ScanState.ORDERING)
    except Exception:
        pass

    scan.purchase_order_ids.append(po_id)

    # Auto-approval path or human-approval path
    if requires_human:
        await state_store.transition_purchase_order(po_id, POState.PENDING_APPROVAL)
        event = await event_store.publish(
            event_type=PO_PENDING_HUMAN_APPROVAL,
            entity_id=po_id,
            payload={"po_id": po_id, "total_cost": po.total_cost, "vendor": vendor.name},
        )
        await message_store.publish(
            agent_name="compliance-gate",
            agent_role="Compliance Gate Agent",
            content=(
                f"PO {po_id} requires human approval: ${po.total_cost:.2f} "
                f"exceeds ${PO_AUTO_APPROVAL_THRESHOLD:.0f} threshold."
            ),
            intent_tag=IntentTag.VALIDATE,
            related_event_ids=[event.id],
        )
    else:
        await state_store.transition_purchase_order(po_id, POState.APPROVED)
        event = await event_store.publish(
            event_type=PO_AUTO_APPROVED,
            entity_id=po_id,
            payload={"po_id": po_id, "total_cost": po.total_cost, "vendor": vendor.name},
        )
        await message_store.publish(
            agent_name="order-manager",
            agent_role="Order Manager Agent",
            content=(
                f"Created PO {po_id} for {vendor.name}: {len(line_items)} items, "
                f"${po.total_cost:.2f} (auto-approved)."
            ),
            intent_tag=IntentTag.EXECUTE,
            related_event_ids=[event.id],
        )

    await event_store.publish(
        event_type=PO_CREATED,
        entity_id=po_id,
        payload={
            "po_id": po_id,
            "scan_id": scan_id,
            "vendor_id": vendor_id,
            "line_items": len(line_items),
            "total_cost": po.total_cost,
            "requires_human_approval": requires_human,
        },
    )

    return {
        "ok": True,
        "po_id": po_id,
        "vendor_id": vendor_id,
        "vendor_name": vendor.name,
        "total_cost": po.total_cost,
        "line_items": len(line_items),
        "requires_human_approval": requires_human,
        "state": str(po.state),
    }


async def approve_purchase_order(
    po_id: str,
    approved: bool = True,
    note: str = "",
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Approve or reject a PO pending human approval."""
    po = state_store.get_purchase_order(po_id)
    if po is None:
        return {"ok": False, "error": f"PO {po_id} not found"}
    if po.state != POState.PENDING_APPROVAL:
        return {"ok": False, "error": f"PO {po_id} is not pending approval (state: {po.state})"}

    if approved:
        await state_store.transition_purchase_order(po_id, POState.APPROVED)
        po.approval_status = POApprovalStatus.HUMAN_APPROVED
        po.approved_at = datetime.now(timezone.utc)
        po.approval_note = note

        event = await event_store.publish(
            event_type=PO_HUMAN_APPROVED,
            entity_id=po_id,
            payload={"po_id": po_id, "note": note},
            state_diff={"from_state": "PENDING_APPROVAL", "to_state": "APPROVED"},
        )
        await message_store.publish(
            agent_name="compliance-gate",
            agent_role="Compliance Gate Agent",
            content=f"PO {po_id} approved by human reviewer. {note}".strip(),
            intent_tag=IntentTag.EXECUTE,
            related_event_ids=[event.id],
        )
    else:
        await state_store.transition_purchase_order(po_id, POState.CANCELLED)
        po.approval_status = POApprovalStatus.HUMAN_REJECTED
        po.approval_note = note

        event = await event_store.publish(
            event_type=PO_HUMAN_REJECTED,
            entity_id=po_id,
            payload={"po_id": po_id, "note": note},
            state_diff={"from_state": "PENDING_APPROVAL", "to_state": "CANCELLED"},
        )
        await message_store.publish(
            agent_name="compliance-gate",
            agent_role="Compliance Gate Agent",
            content=f"PO {po_id} rejected by human reviewer. {note}".strip(),
            intent_tag=IntentTag.ESCALATE,
            related_event_ids=[event.id],
        )

    return {"ok": True, "po_id": po_id, "approved": approved, "state": str(po.state)}


async def submit_purchase_order(
    po_id: str,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Submit an approved PO to the vendor."""
    po = state_store.get_purchase_order(po_id)
    if po is None:
        return {"ok": False, "error": f"PO {po_id} not found"}

    try:
        await state_store.transition_purchase_order(po_id, POState.SUBMITTED)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    po.submitted_at = datetime.now(timezone.utc)

    event = await event_store.publish(
        event_type=PO_SUBMITTED,
        entity_id=po_id,
        payload={"po_id": po_id, "vendor_id": po.vendor_id},
        state_diff={"from_state": "APPROVED", "to_state": "SUBMITTED"},
    )

    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=f"PO {po_id} submitted to vendor {po.vendor_name}.",
        intent_tag=IntentTag.EXECUTE,
        related_event_ids=[event.id],
    )

    return {"ok": True, "po_id": po_id, "state": str(po.state)}


# ── Fulfillment ─────────────────────────────────────────────────────

async def create_shipment(
    po_id: str,
    carrier: str,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Create a shipment for a confirmed PO."""
    po = state_store.get_purchase_order(po_id)
    if po is None:
        return {"ok": False, "error": f"PO {po_id} not found"}

    vendor = state_store.get_vendor(po.vendor_id)
    lead_days = vendor.lead_time_days if vendor else 5

    shipment_id = f"SHP-{uuid.uuid4().hex[:8].upper()}"
    tracking_number = f"TRK-{uuid.uuid4().hex[:8].upper()}"
    expected_delivery = datetime.now(timezone.utc) + timedelta(days=lead_days)

    shipment = Shipment(
        id=shipment_id,
        po_id=po_id,
        vendor_id=po.vendor_id,
        closet_id=po.closet_id,
        carrier=carrier,
        tracking_number=tracking_number,
        expected_delivery=expected_delivery,
        items_count=len(po.line_items),
    )
    state_store.shipments[shipment_id] = shipment

    # Transition PO to SHIPPED
    try:
        await state_store.transition_purchase_order(po_id, POState.SHIPPED)
    except Exception:
        pass  # PO may not be in correct state

    event = await event_store.publish(
        event_type=SHIPMENT_CREATED,
        entity_id=shipment_id,
        payload={
            "shipment_id": shipment_id,
            "po_id": po_id,
            "carrier": carrier,
            "tracking_number": tracking_number,
            "expected_delivery": expected_delivery.isoformat(),
        },
    )

    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=(
            f"Shipment {shipment_id} created for PO {po_id}: "
            f"{carrier}, tracking {tracking_number}, "
            f"expected delivery {expected_delivery.date().isoformat()}."
        ),
        intent_tag=IntentTag.EXECUTE,
        related_event_ids=[event.id],
    )

    return {
        "ok": True,
        "shipment_id": shipment_id,
        "po_id": po_id,
        "tracking_number": tracking_number,
        "carrier": carrier,
        "expected_delivery": expected_delivery.isoformat(),
    }


async def receive_shipment(
    shipment_id: str,
    *,
    state_store: StateStore,
    event_store: EventStore,
    message_store: MessageStore,
) -> dict:
    """Mark a shipment as delivered and restock closet items."""
    shipment = state_store.get_shipment(shipment_id)
    if shipment is None:
        return {"ok": False, "error": f"Shipment {shipment_id} not found"}

    # Transition shipment → DELIVERED
    try:
        await state_store.transition_shipment(shipment_id, ShipmentState.DELIVERED)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    shipment.delivered_at = datetime.now(timezone.utc)

    # Transition PO → RECEIVED
    try:
        await state_store.transition_purchase_order(shipment.po_id, POState.RECEIVED)
    except Exception:
        pass

    # Restock items: find the PO and increment supply item quantities
    po = state_store.get_purchase_order(shipment.po_id)
    restocked_items = []
    if po:
        for line in po.line_items:
            # Find the supply item by SKU in the shipment's closet
            matching = state_store.get_items(
                filter_fn=lambda i, sku=line.item_sku, cid=shipment.closet_id: (
                    i.sku == sku and i.closet_id == cid
                )
            )
            for item in matching:
                item.current_quantity += line.quantity
                item.last_restocked = datetime.now(timezone.utc)
                restocked_items.append({
                    "item_id": item.id,
                    "sku": item.sku,
                    "quantity_added": line.quantity,
                    "new_quantity": item.current_quantity,
                })

    event = await event_store.publish(
        event_type=SHIPMENT_DELIVERED,
        entity_id=shipment_id,
        payload={"shipment_id": shipment_id, "po_id": shipment.po_id},
        state_diff={"from_state": "IN_TRANSIT", "to_state": "DELIVERED"},
    )

    if restocked_items:
        await event_store.publish(
            event_type=CLOSET_RESTOCKED,
            entity_id=shipment.closet_id,
            payload={"shipment_id": shipment_id, "items_restocked": restocked_items},
        )

    await message_store.publish(
        agent_name="order-manager",
        agent_role="Order Manager Agent",
        content=(
            f"Shipment {shipment_id} delivered. "
            f"Restocked {len(restocked_items)} items in closet {shipment.closet_id}."
        ),
        intent_tag=IntentTag.EXECUTE,
        related_event_ids=[event.id],
    )

    return {
        "ok": True,
        "shipment_id": shipment_id,
        "po_id": shipment.po_id,
        "items_restocked": len(restocked_items),
    }


# ── Generic event emission ──────────────────────────────────────────

async def publish_event(
    event_type: str,
    entity_id: str,
    payload: Optional[dict] = None,
    *,
    event_store: EventStore,
    **_kwargs,
) -> dict:
    """Emit a generic event."""
    event = await event_store.publish(
        event_type=event_type,
        entity_id=entity_id,
        payload=payload or {},
    )
    return {"ok": True, "event_id": event.id, "sequence": event.sequence}


# ── Escalation ──────────────────────────────────────────────────────

async def escalate(
    issue_type: str,
    entity_id: str,
    severity: str,
    message: str,
    *,
    event_store: EventStore,
    message_store: MessageStore,
    **_kwargs,
) -> dict:
    """Emit a CriticalShortageDetected event and publish an escalation message."""
    event = await event_store.publish(
        event_type=CRITICAL_SHORTAGE_DETECTED,
        entity_id=entity_id,
        payload={"issue_type": issue_type, "severity": severity, "message": message},
    )

    await message_store.publish(
        agent_name="compliance-gate",
        agent_role="Compliance Gate Agent",
        content=f"ESCALATION [{severity}]: {issue_type} — {message} (entity: {entity_id})",
        intent_tag=IntentTag.ESCALATE,
        related_event_ids=[event.id],
    )

    return {"ok": True, "event_id": event.id, "issue_type": issue_type, "severity": severity}
