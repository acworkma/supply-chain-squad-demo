"""
Tool function tests — every agent-callable tool (ADR-003/003a).

Each tool receives state_store, event_store, message_store as kwargs.
We verify state mutations, event emissions, message publishing, and error paths.
"""

import pytest

from app.events.event_store import EventStore
from app.messages.message_store import MessageStore
from app.models.entities import (
    CatalogEntry,
    PurchaseOrder,
    ReorderItem,
    ScanResult,
    Shipment,
    SupplyCloset,
    SupplyItem,
    Vendor,
)
from app.models.enums import (
    ContractTier,
    IntentTag,
    ItemCategory,
    ItemCriticality,
    POApprovalStatus,
    POState,
    ScanState,
    ShipmentState,
    VendorStockStatus,
)
from app.models.events import (
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
from app.state.store import StateStore
from app.tools.tool_functions import (
    analyze_scan,
    approve_purchase_order,
    create_purchase_order,
    create_shipment,
    escalate,
    get_items,
    get_purchase_orders,
    get_scan,
    get_shipments,
    get_vendors,
    initiate_scan,
    lookup_vendor_catalog,
    publish_event,
    receive_shipment,
    submit_purchase_order,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _seed_closet(store: StateStore, closet_id: str = "CLO-ICU-01") -> SupplyCloset:
    closet = SupplyCloset(id=closet_id, name="ICU Supply Closet", floor="floor-2", unit="ICU", location="2nd Floor East Wing")
    store.closets[closet_id] = closet
    return closet


def _seed_item(
    store: StateStore,
    item_id: str = "ITEM-001",
    closet_id: str = "CLO-ICU-01",
    sku: str = "SKU-NS-1000",
    current_qty: int = 5,
    par_level: int = 20,
) -> SupplyItem:
    item = SupplyItem(
        id=item_id, sku=sku, name="Normal Saline 1000mL", closet_id=closet_id,
        category=ItemCategory.IV_THERAPY, criticality=ItemCriticality.CRITICAL,
        par_level=par_level, reorder_quantity=30, current_quantity=current_qty,
        unit_of_measure="bag", consumption_rate_per_day=4.0,
    )
    store.items[item_id] = item
    return item


def _seed_vendor(store: StateStore, vendor_id: str = "VND-MED-01") -> Vendor:
    vendor = Vendor(
        id=vendor_id, name="MedLine Industries", contract_tier=ContractTier.GPO_CONTRACT,
        lead_time_days=3, expedite_lead_time_days=1, minimum_order_value=100.0,
    )
    store.vendors[vendor_id] = vendor
    return vendor


def _seed_catalog_entry(
    store: StateStore,
    entry_id: str = "CAT-001",
    vendor_id: str = "VND-MED-01",
    item_sku: str = "SKU-NS-1000",
    unit_price: float = 8.50,
) -> CatalogEntry:
    entry = CatalogEntry(
        id=entry_id, vendor_id=vendor_id, item_sku=item_sku,
        unit_price=unit_price, contract_tier=ContractTier.GPO_CONTRACT,
        stock_status=VendorStockStatus.IN_STOCK, lead_time_days=3,
    )
    store.catalog[entry_id] = entry
    return entry


def _seed_scan_with_reorder(store: StateStore, scan_id: str = "SCAN-001", closet_id: str = "CLO-ICU-01") -> ScanResult:
    """Create a scan in ITEMS_IDENTIFIED state with reorder items."""
    scan = ScanResult(
        id=scan_id, closet_id=closet_id, state=ScanState.ITEMS_IDENTIFIED,
        items_scanned=5, items_below_par=1,
        items_to_reorder=[
            ReorderItem(
                item_id="ITEM-001", item_sku="SKU-NS-1000", item_name="Normal Saline 1000mL",
                current_quantity=5, par_level=20, reorder_quantity=30,
                criticality=ItemCriticality.CRITICAL, days_until_stockout=1.25,
                recommended_vendor_id="VND-MED-01", recommended_unit_price=8.50,
            ),
        ],
    )
    store.scans[scan_id] = scan
    return scan


# ===================================================================
# get_scan
# ===================================================================

class TestGetScan:

    async def test_returns_scan_data(self, state_store: StateStore):
        scan = ScanResult(id="SCAN-001", closet_id="CLO-ICU-01")
        state_store.scans["SCAN-001"] = scan
        result = await get_scan("SCAN-001", state_store=state_store)
        assert result["ok"] is True
        assert result["scan"]["id"] == "SCAN-001"
        assert result["scan"]["closet_id"] == "CLO-ICU-01"

    async def test_not_found(self, state_store: StateStore):
        result = await get_scan("SCAN-MISSING", state_store=state_store)
        assert result["ok"] is False
        assert "not found" in result["error"]


# ===================================================================
# get_items
# ===================================================================

class TestGetItems:

    async def test_returns_all_items(self, state_store: StateStore):
        _seed_closet(state_store, "CLO-1")
        _seed_item(state_store, "ITEM-1", closet_id="CLO-1")
        _seed_item(state_store, "ITEM-2", closet_id="CLO-1", sku="SKU-GLOVE")
        result = await get_items(state_store=state_store)
        assert result["ok"] is True
        assert len(result["items"]) == 2

    async def test_filter_by_closet(self, state_store: StateStore):
        _seed_closet(state_store, "CLO-1")
        _seed_closet(state_store, "CLO-2")
        _seed_item(state_store, "ITEM-1", closet_id="CLO-1")
        _seed_item(state_store, "ITEM-2", closet_id="CLO-2", sku="SKU-GLOVE")
        result = await get_items(state_store=state_store, closet_id="CLO-1")
        assert len(result["items"]) == 1
        assert result["items"][0]["closet_id"] == "CLO-1"

    async def test_filter_by_category(self, state_store: StateStore):
        _seed_closet(state_store)
        _seed_item(state_store, "ITEM-1")
        result = await get_items(state_store=state_store, category="IV_THERAPY")
        assert len(result["items"]) == 1

    async def test_filter_by_criticality(self, state_store: StateStore):
        _seed_closet(state_store)
        _seed_item(state_store, "ITEM-1")
        result = await get_items(state_store=state_store, criticality="CRITICAL")
        assert len(result["items"]) == 1

    async def test_empty_store(self, state_store: StateStore):
        result = await get_items(state_store=state_store)
        assert result["ok"] is True
        assert result["items"] == []


# ===================================================================
# get_vendors
# ===================================================================

class TestGetVendors:

    async def test_returns_all_vendors(self, state_store: StateStore):
        _seed_vendor(state_store, "VND-1")
        _seed_vendor(state_store, "VND-2")
        result = await get_vendors(state_store=state_store)
        assert result["ok"] is True
        assert len(result["vendors"]) == 2

    async def test_filter_by_contract_tier(self, state_store: StateStore):
        _seed_vendor(state_store, "VND-1")
        result = await get_vendors(state_store=state_store, contract_tier="GPO_CONTRACT")
        assert len(result["vendors"]) == 1


# ===================================================================
# get_purchase_orders
# ===================================================================

class TestGetPurchaseOrders:

    async def test_returns_all_pos(self, state_store: StateStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test")
        state_store.purchase_orders["PO-1"] = po
        result = await get_purchase_orders(state_store=state_store)
        assert result["ok"] is True
        assert len(result["purchase_orders"]) == 1

    async def test_filter_by_state(self, state_store: StateStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test", state=POState.APPROVED)
        state_store.purchase_orders["PO-1"] = po
        result = await get_purchase_orders(state_store=state_store, po_state="APPROVED")
        assert len(result["purchase_orders"]) == 1

    async def test_empty_store(self, state_store: StateStore):
        result = await get_purchase_orders(state_store=state_store)
        assert result["ok"] is True
        assert result["purchase_orders"] == []


# ===================================================================
# get_shipments
# ===================================================================

class TestGetShipments:

    async def test_returns_all_shipments(self, state_store: StateStore):
        shp = Shipment(id="SHP-1", po_id="PO-1", vendor_id="V-1", closet_id="CLO-1")
        state_store.shipments["SHP-1"] = shp
        result = await get_shipments(state_store=state_store)
        assert result["ok"] is True
        assert len(result["shipments"]) == 1

    async def test_filter_by_state(self, state_store: StateStore):
        shp = Shipment(id="SHP-1", po_id="PO-1", vendor_id="V-1", closet_id="CLO-1", state=ShipmentState.SHIPPED)
        state_store.shipments["SHP-1"] = shp
        result = await get_shipments(state_store=state_store, shipment_state="SHIPPED")
        assert len(result["shipments"]) == 1

    async def test_empty_store(self, state_store: StateStore):
        result = await get_shipments(state_store=state_store)
        assert result["ok"] is True
        assert result["shipments"] == []


# ===================================================================
# initiate_scan
# ===================================================================

class TestInitiateScan:

    async def test_creates_scan(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store, "CLO-ICU-01")
        result = await initiate_scan("CLO-ICU-01", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["closet_id"] == "CLO-ICU-01"
        assert "scan_id" in result

    async def test_scan_stored_in_state(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store, "CLO-ICU-01")
        result = await initiate_scan("CLO-ICU-01", state_store=state_store, event_store=event_store, message_store=message_store)
        scan = state_store.get_scan(result["scan_id"])
        assert scan is not None
        assert scan.state == ScanState.INITIATED
        assert scan.closet_id == "CLO-ICU-01"

    async def test_emits_scan_initiated_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store, "CLO-ICU-01")
        await initiate_scan("CLO-ICU-01", state_store=state_store, event_store=event_store, message_store=message_store)
        events = event_store.get_events()
        assert len(events) == 1
        assert events[0].event_type == CLOSET_SCAN_INITIATED

    async def test_publishes_message(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store, "CLO-ICU-01")
        await initiate_scan("CLO-ICU-01", state_store=state_store, event_store=event_store, message_store=message_store)
        messages = message_store.get_messages()
        assert len(messages) == 1
        assert messages[0].agent_name == "supply-scanner"
        assert messages[0].intent_tag == IntentTag.EXECUTE

    async def test_closet_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await initiate_scan("CLO-FAKE", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "not found" in result["error"]


# ===================================================================
# analyze_scan
# ===================================================================

class TestAnalyzeScan:

    async def test_identifies_items_below_par(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_item(state_store, "ITEM-1", current_qty=5, par_level=20)
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store)
        scan = ScanResult(id="SCAN-001", closet_id="CLO-ICU-01")
        state_store.scans["SCAN-001"] = scan

        result = await analyze_scan("SCAN-001", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["items_below_par"] == 1
        assert result["items_scanned"] == 1
        assert len(result["reorder_items"]) == 1

    async def test_transitions_scan_state(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_item(state_store)
        _seed_catalog_entry(state_store)
        scan = ScanResult(id="SCAN-001", closet_id="CLO-ICU-01")
        state_store.scans["SCAN-001"] = scan

        await analyze_scan("SCAN-001", state_store=state_store, event_store=event_store, message_store=message_store)
        assert state_store.get_scan("SCAN-001").state == ScanState.ITEMS_IDENTIFIED

    async def test_computes_days_until_stockout(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_item(state_store, current_qty=8, par_level=20)  # 8 bags / 4 per day = 2.0 days
        _seed_catalog_entry(state_store)
        scan = ScanResult(id="SCAN-001", closet_id="CLO-ICU-01")
        state_store.scans["SCAN-001"] = scan

        result = await analyze_scan("SCAN-001", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["reorder_items"][0]["days_until_stockout"] == 2.0

    async def test_emits_items_below_par_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_item(state_store)
        _seed_catalog_entry(state_store)
        scan = ScanResult(id="SCAN-001", closet_id="CLO-ICU-01")
        state_store.scans["SCAN-001"] = scan

        await analyze_scan("SCAN-001", state_store=state_store, event_store=event_store, message_store=message_store)
        events = event_store.get_events()
        event_types = [e.event_type for e in events]
        assert ITEMS_BELOW_PAR_IDENTIFIED in event_types

    async def test_no_items_below_par(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_item(state_store, current_qty=25, par_level=20)  # Above par
        scan = ScanResult(id="SCAN-001", closet_id="CLO-ICU-01")
        state_store.scans["SCAN-001"] = scan

        result = await analyze_scan("SCAN-001", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["items_below_par"] == 0

    async def test_scan_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await analyze_scan("SCAN-FAKE", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "not found" in result["error"]


# ===================================================================
# lookup_vendor_catalog
# ===================================================================

class TestLookupVendorCatalog:

    async def test_finds_catalog_entries(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store)
        result = await lookup_vendor_catalog("SKU-NS-1000", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert len(result["entries"]) == 1
        assert result["recommended_vendor_id"] == "VND-MED-01"

    async def test_sku_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await lookup_vendor_catalog("SKU-NONEXISTENT", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "No catalog entries" in result["error"]

    async def test_emits_vendor_lookup_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store)
        await lookup_vendor_catalog("SKU-NS-1000", state_store=state_store, event_store=event_store, message_store=message_store)
        events = event_store.get_events()
        assert events[0].event_type == VENDOR_LOOKUP_COMPLETED

    async def test_publishes_message(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store)
        await lookup_vendor_catalog("SKU-NS-1000", state_store=state_store, event_store=event_store, message_store=message_store)
        messages = message_store.get_messages()
        assert messages[0].agent_name == "catalog-sourcer"
        assert messages[0].intent_tag == IntentTag.PROPOSE

    async def test_recommends_cheapest_in_stock_gpo(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_vendor(state_store, "VND-1")
        _seed_catalog_entry(store=state_store, entry_id="CAT-1", vendor_id="VND-1", unit_price=10.0)
        vendor2 = Vendor(id="VND-2", name="SpotVendor", contract_tier=ContractTier.SPOT_BUY, lead_time_days=5, expedite_lead_time_days=2, minimum_order_value=50.0)
        state_store.vendors["VND-2"] = vendor2
        entry2 = CatalogEntry(id="CAT-2", vendor_id="VND-2", item_sku="SKU-NS-1000", unit_price=7.0, contract_tier=ContractTier.SPOT_BUY, stock_status=VendorStockStatus.IN_STOCK, lead_time_days=5)
        state_store.catalog["CAT-2"] = entry2

        result = await lookup_vendor_catalog("SKU-NS-1000", state_store=state_store, event_store=event_store, message_store=message_store)
        # GPO contract (VND-1) should be recommended over cheaper spot buy (VND-2)
        assert result["recommended_vendor_id"] == "VND-1"


# ===================================================================
# create_purchase_order
# ===================================================================

class TestCreatePurchaseOrder:

    async def test_creates_po_auto_approved(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store)
        _seed_scan_with_reorder(state_store)  # 30 × $8.50 = $255 < $1000

        result = await create_purchase_order("SCAN-001", "VND-MED-01", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["requires_human_approval"] is False
        assert result["total_cost"] == 255.0
        assert result["line_items"] == 1
        assert result["state"] == "APPROVED"

    async def test_po_stored_in_state(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store)
        _seed_scan_with_reorder(state_store)

        result = await create_purchase_order("SCAN-001", "VND-MED-01", state_store=state_store, event_store=event_store, message_store=message_store)
        po = state_store.get_purchase_order(result["po_id"])
        assert po is not None
        assert po.state == POState.APPROVED
        assert po.vendor_name == "MedLine Industries"

    async def test_emits_po_auto_approved_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store)
        _seed_scan_with_reorder(state_store)

        await create_purchase_order("SCAN-001", "VND-MED-01", state_store=state_store, event_store=event_store, message_store=message_store)
        event_types = [e.event_type for e in event_store.get_events()]
        assert PO_AUTO_APPROVED in event_types
        assert PO_CREATED in event_types

    async def test_requires_human_approval_over_threshold(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store, unit_price=50.0)  # 30 × $50 = $1500 >= $1000
        scan = ScanResult(
            id="SCAN-BIG", closet_id="CLO-ICU-01", state=ScanState.ITEMS_IDENTIFIED,
            items_below_par=1,
            items_to_reorder=[
                ReorderItem(
                    item_id="ITEM-001", item_sku="SKU-NS-1000", item_name="Normal Saline",
                    current_quantity=5, par_level=20, reorder_quantity=30,
                    criticality=ItemCriticality.CRITICAL, days_until_stockout=1.25,
                    recommended_unit_price=50.0,
                ),
            ],
        )
        state_store.scans["SCAN-BIG"] = scan

        result = await create_purchase_order("SCAN-BIG", "VND-MED-01", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["requires_human_approval"] is True
        assert result["state"] == "PENDING_APPROVAL"

    async def test_emits_pending_human_approval_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store, unit_price=50.0)
        scan = ScanResult(
            id="SCAN-BIG", closet_id="CLO-ICU-01", state=ScanState.ITEMS_IDENTIFIED,
            items_below_par=1,
            items_to_reorder=[
                ReorderItem(
                    item_id="ITEM-001", item_sku="SKU-NS-1000", item_name="Normal Saline",
                    current_quantity=5, par_level=20, reorder_quantity=30,
                    criticality=ItemCriticality.CRITICAL, days_until_stockout=1.25,
                    recommended_unit_price=50.0,
                ),
            ],
        )
        state_store.scans["SCAN-BIG"] = scan

        await create_purchase_order("SCAN-BIG", "VND-MED-01", state_store=state_store, event_store=event_store, message_store=message_store)
        event_types = [e.event_type for e in event_store.get_events()]
        assert PO_PENDING_HUMAN_APPROVAL in event_types

    async def test_scan_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await create_purchase_order("SCAN-FAKE", "VND-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_vendor_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_scan_with_reorder(state_store)
        result = await create_purchase_order("SCAN-001", "VND-FAKE", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_no_items_to_reorder(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_vendor(state_store)
        scan = ScanResult(id="SCAN-EMPTY", closet_id="CLO-1", state=ScanState.ITEMS_IDENTIFIED)
        state_store.scans["SCAN-EMPTY"] = scan
        result = await create_purchase_order("SCAN-EMPTY", "VND-MED-01", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "no items to reorder" in result["error"]


# ===================================================================
# approve_purchase_order
# ===================================================================

class TestApprovePurchaseOrder:

    async def test_approves_pending_po(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test", state=POState.PENDING_APPROVAL)
        state_store.purchase_orders["PO-1"] = po
        result = await approve_purchase_order("PO-1", approved=True, note="Looks good", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["approved"] is True
        assert state_store.get_purchase_order("PO-1").state == POState.APPROVED

    async def test_rejects_pending_po(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test", state=POState.PENDING_APPROVAL)
        state_store.purchase_orders["PO-1"] = po
        result = await approve_purchase_order("PO-1", approved=False, note="Too expensive", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["approved"] is False
        assert state_store.get_purchase_order("PO-1").state == POState.CANCELLED

    async def test_emits_human_approved_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test", state=POState.PENDING_APPROVAL)
        state_store.purchase_orders["PO-1"] = po
        await approve_purchase_order("PO-1", approved=True, state_store=state_store, event_store=event_store, message_store=message_store)
        assert any(e.event_type == PO_HUMAN_APPROVED for e in event_store.get_events())

    async def test_emits_human_rejected_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test", state=POState.PENDING_APPROVAL)
        state_store.purchase_orders["PO-1"] = po
        await approve_purchase_order("PO-1", approved=False, state_store=state_store, event_store=event_store, message_store=message_store)
        assert any(e.event_type == PO_HUMAN_REJECTED for e in event_store.get_events())

    async def test_po_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await approve_purchase_order("PO-FAKE", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False

    async def test_po_not_pending_returns_error(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test", state=POState.APPROVED)
        state_store.purchase_orders["PO-1"] = po
        result = await approve_purchase_order("PO-1", approved=True, state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False
        assert "not pending approval" in result["error"]


# ===================================================================
# submit_purchase_order
# ===================================================================

class TestSubmitPurchaseOrder:

    async def test_submits_approved_po(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test", state=POState.APPROVED)
        state_store.purchase_orders["PO-1"] = po
        result = await submit_purchase_order("PO-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert state_store.get_purchase_order("PO-1").state == POState.SUBMITTED

    async def test_emits_po_submitted_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test", state=POState.APPROVED)
        state_store.purchase_orders["PO-1"] = po
        await submit_purchase_order("PO-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert any(e.event_type == PO_SUBMITTED for e in event_store.get_events())

    async def test_po_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await submit_purchase_order("PO-FAKE", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False

    async def test_invalid_state_returns_error(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="V-1", vendor_name="Test", state=POState.CREATED)
        state_store.purchase_orders["PO-1"] = po
        result = await submit_purchase_order("PO-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False


# ===================================================================
# create_shipment
# ===================================================================

class TestCreateShipment:

    async def test_creates_shipment(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_vendor(state_store)
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="VND-MED-01", vendor_name="MedLine", state=POState.CONFIRMED, closet_id="CLO-1")
        state_store.purchase_orders["PO-1"] = po
        result = await create_shipment("PO-1", "MedLine Logistics", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert "shipment_id" in result
        assert "tracking_number" in result
        assert result["carrier"] == "MedLine Logistics"

    async def test_shipment_stored_in_state(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_vendor(state_store)
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="VND-MED-01", vendor_name="MedLine", state=POState.CONFIRMED, closet_id="CLO-1")
        state_store.purchase_orders["PO-1"] = po
        result = await create_shipment("PO-1", "MedLine Logistics", state_store=state_store, event_store=event_store, message_store=message_store)
        shipment = state_store.get_shipment(result["shipment_id"])
        assert shipment is not None
        assert shipment.po_id == "PO-1"
        assert shipment.carrier == "MedLine Logistics"

    async def test_emits_shipment_created_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_vendor(state_store)
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="VND-MED-01", vendor_name="MedLine", state=POState.CONFIRMED, closet_id="CLO-1")
        state_store.purchase_orders["PO-1"] = po
        await create_shipment("PO-1", "MedLine Logistics", state_store=state_store, event_store=event_store, message_store=message_store)
        assert any(e.event_type == SHIPMENT_CREATED for e in event_store.get_events())

    async def test_po_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await create_shipment("PO-FAKE", "Carrier", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False


# ===================================================================
# receive_shipment
# ===================================================================

class TestReceiveShipment:

    async def test_receives_shipment_and_restocks(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_item(state_store, current_qty=5)
        _seed_vendor(state_store)
        _seed_catalog_entry(state_store)

        from app.models.entities import POLineItem
        po = PurchaseOrder(
            id="PO-1", scan_id="S-1", vendor_id="VND-MED-01", vendor_name="MedLine",
            state=POState.SHIPPED, closet_id="CLO-ICU-01",
            line_items=[POLineItem(item_sku="SKU-NS-1000", item_name="Normal Saline", quantity=30, unit_price=8.50, extended_price=255.0, contract_tier=ContractTier.GPO_CONTRACT, criticality=ItemCriticality.CRITICAL)],
        )
        state_store.purchase_orders["PO-1"] = po

        shp = Shipment(id="SHP-1", po_id="PO-1", vendor_id="VND-MED-01", closet_id="CLO-ICU-01", state=ShipmentState.IN_TRANSIT)
        state_store.shipments["SHP-1"] = shp

        result = await receive_shipment("SHP-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is True
        assert result["items_restocked"] == 1

        # Item should now have 5 + 30 = 35
        item = state_store.get_item("ITEM-001")
        assert item.current_quantity == 35

    async def test_transitions_shipment_to_delivered(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_vendor(state_store)
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="VND-MED-01", vendor_name="MedLine", state=POState.SHIPPED, closet_id="CLO-ICU-01")
        state_store.purchase_orders["PO-1"] = po
        shp = Shipment(id="SHP-1", po_id="PO-1", vendor_id="VND-MED-01", closet_id="CLO-ICU-01", state=ShipmentState.IN_TRANSIT)
        state_store.shipments["SHP-1"] = shp

        await receive_shipment("SHP-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert state_store.get_shipment("SHP-1").state == ShipmentState.DELIVERED

    async def test_emits_shipment_delivered_event(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        _seed_closet(state_store)
        _seed_vendor(state_store)
        po = PurchaseOrder(id="PO-1", scan_id="S-1", vendor_id="VND-MED-01", vendor_name="MedLine", state=POState.SHIPPED, closet_id="CLO-ICU-01")
        state_store.purchase_orders["PO-1"] = po
        shp = Shipment(id="SHP-1", po_id="PO-1", vendor_id="VND-MED-01", closet_id="CLO-ICU-01", state=ShipmentState.IN_TRANSIT)
        state_store.shipments["SHP-1"] = shp

        await receive_shipment("SHP-1", state_store=state_store, event_store=event_store, message_store=message_store)
        assert any(e.event_type == SHIPMENT_DELIVERED for e in event_store.get_events())

    async def test_shipment_not_found(self, state_store: StateStore, event_store: EventStore, message_store: MessageStore):
        result = await receive_shipment("SHP-FAKE", state_store=state_store, event_store=event_store, message_store=message_store)
        assert result["ok"] is False


# ===================================================================
# publish_event
# ===================================================================

class TestPublishEvent:

    async def test_emits_generic_event(self, event_store: EventStore):
        result = await publish_event("CustomEvent", "entity-1", {"key": "value"}, event_store=event_store)
        assert result["ok"] is True
        assert "event_id" in result
        assert result["sequence"] >= 1

    async def test_event_stored(self, event_store: EventStore):
        await publish_event("CustomEvent", "entity-1", event_store=event_store)
        events = event_store.get_events()
        assert len(events) == 1
        assert events[0].event_type == "CustomEvent"

    async def test_empty_payload_defaults(self, event_store: EventStore):
        await publish_event("Test", "e-1", event_store=event_store)
        events = event_store.get_events()
        assert events[0].payload == {}


# ===================================================================
# escalate
# ===================================================================

class TestEscalate:

    async def test_emits_critical_shortage_event(self, event_store: EventStore, message_store: MessageStore):
        result = await escalate(
            "critical_shortage", "ITEM-001", "HIGH", "IV saline critically low",
            event_store=event_store, message_store=message_store,
        )
        assert result["ok"] is True
        assert result["issue_type"] == "critical_shortage"
        assert result["severity"] == "HIGH"

    async def test_event_type_is_critical_shortage(self, event_store: EventStore, message_store: MessageStore):
        await escalate(
            "critical_shortage", "ITEM-001", "HIGH", "IV saline critically low",
            event_store=event_store, message_store=message_store,
        )
        events = event_store.get_events()
        assert events[0].event_type == CRITICAL_SHORTAGE_DETECTED
        assert events[0].payload["severity"] == "HIGH"

    async def test_publishes_escalation_message(self, event_store: EventStore, message_store: MessageStore):
        await escalate(
            "critical_shortage", "ITEM-001", "HIGH", "IV saline critically low",
            event_store=event_store, message_store=message_store,
        )
        messages = message_store.get_messages()
        assert len(messages) == 1
        assert messages[0].intent_tag == IntentTag.ESCALATE
        assert messages[0].agent_name == "compliance-gate"
        assert "ESCALATION" in messages[0].content
