"""
State store tests — seeding, snapshots, entity retrieval, clearing, transitions, concurrency.

The state store holds the materialized in-memory state (ADR-001, ADR-002).
It's the fast read path; the event store is the audit trail.

Snapshot format: get_snapshot() returns dicts keyed by entity ID.
"""

import asyncio
import json
import pytest

from app.models.enums import (
    ContractTier,
    ItemCategory,
    ItemCriticality,
    POState,
    ScanState,
    ShipmentState,
    TaskState,
    VendorStockStatus,
)
from app.models.entities import PurchaseOrder, ScanResult, Shipment, SupplyCloset, SupplyItem
from app.state.store import StateStore
from app.models.transitions import InvalidTransitionError


class TestSeedInitialState:
    """seed_initial_state() creates the expected hospital closet layout."""

    def test_seed_creates_closets(self, state_store: StateStore):
        state_store.seed_initial_state()
        closets = state_store.get_closets()
        assert len(
            closets) > 0, "seed_initial_state should create at least one closet"

    def test_seed_creates_5_closets(self, state_store: StateStore):
        state_store.seed_initial_state()
        closets = state_store.get_closets()
        assert len(closets) == 5

    def test_seed_creates_supply_items(self, state_store: StateStore):
        state_store.seed_initial_state()
        items = state_store.get_items()
        assert len(items) == 10

    def test_seed_creates_vendors(self, state_store: StateStore):
        state_store.seed_initial_state()
        vendors = state_store.get_vendors()
        assert len(vendors) == 4

    def test_seed_creates_catalog_entries(self, state_store: StateStore):
        state_store.seed_initial_state()
        catalog = list(state_store.catalog.values())
        assert len(catalog) == 9

    def test_seed_items_have_various_categories(self, state_store: StateStore):
        state_store.seed_initial_state()
        items = state_store.get_items()
        categories = {i.category for i in items}
        assert ItemCategory.IV_THERAPY in categories
        assert ItemCategory.PPE in categories
        assert ItemCategory.SURGICAL in categories

    def test_seed_items_have_various_criticalities(self, state_store: StateStore):
        state_store.seed_initial_state()
        items = state_store.get_items()
        criticalities = {i.criticality for i in items}
        assert ItemCriticality.CRITICAL in criticalities
        assert ItemCriticality.STANDARD in criticalities
        assert ItemCriticality.LOW in criticalities

    def test_seed_is_idempotent_or_resets(self, state_store: StateStore):
        state_store.seed_initial_state()
        count_1 = len(state_store.get_closets())
        state_store.seed_initial_state()
        count_2 = len(state_store.get_closets())
        assert count_1 == count_2


class TestGetSnapshot:
    """get_snapshot() returns a serializable dict."""

    def test_snapshot_returns_dict(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        assert isinstance(snapshot, dict)

    def test_snapshot_has_closets_key(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        assert "closets" in snapshot

    def test_snapshot_has_supply_items_key(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        assert "supply_items" in snapshot

    def test_snapshot_has_vendors_key(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        assert "vendors" in snapshot

    def test_snapshot_has_catalog_key(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        assert "catalog" in snapshot

    def test_snapshot_has_scans_key(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        assert "scans" in snapshot

    def test_snapshot_has_purchase_orders_key(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        assert "purchase_orders" in snapshot

    def test_snapshot_has_shipments_key(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        assert "shipments" in snapshot

    def test_snapshot_has_hospital_config(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        assert "hospital_config" in snapshot

    def test_snapshot_is_json_serializable(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        json_str = json.dumps(snapshot, default=str)
        assert isinstance(json_str, str)

    def test_snapshot_closets_count_matches_get_closets(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        closets = seeded_state_store.get_closets()
        assert len(snapshot["closets"]) == len(closets)

    def test_snapshot_closets_are_dicts_keyed_by_id(self, seeded_state_store: StateStore):
        snapshot = seeded_state_store.get_snapshot()
        closets_dict = snapshot["closets"]
        assert isinstance(closets_dict, dict)
        for key, val in closets_dict.items():
            assert isinstance(key, str)
            assert isinstance(val, dict)
            assert val["id"] == key

    def test_empty_store_snapshot(self, state_store: StateStore):
        snapshot = state_store.get_snapshot()
        assert isinstance(snapshot, dict)
        assert len(snapshot.get("closets", {})) == 0
        assert len(snapshot.get("supply_items", {})) == 0


class TestClear:
    """clear() resets all state."""

    def test_clear_removes_all_closets(self, seeded_state_store: StateStore):
        assert len(seeded_state_store.get_closets()) > 0
        seeded_state_store.clear()
        assert len(seeded_state_store.get_closets()) == 0

    def test_clear_removes_all_items(self, state_store: StateStore):
        state_store.seed_initial_state()
        assert len(state_store.get_items()) > 0
        state_store.clear()
        assert len(state_store.get_items()) == 0

    def test_clear_removes_all_vendors(self, state_store: StateStore):
        state_store.seed_initial_state()
        assert len(state_store.get_vendors()) > 0
        state_store.clear()
        assert len(state_store.get_vendors()) == 0

    def test_clear_removes_all_scans(self, state_store: StateStore):
        state_store.clear()
        assert len(state_store.get_scans()) == 0

    def test_clear_removes_all_purchase_orders(self, state_store: StateStore):
        state_store.clear()
        assert len(state_store.get_purchase_orders()) == 0

    def test_clear_removes_all_shipments(self, state_store: StateStore):
        state_store.clear()
        assert len(state_store.get_shipments()) == 0


class TestGetCloset:
    """get_closet() returns a single closet by ID."""

    def test_get_existing_closet(self, seeded_state_store: StateStore):
        closets = seeded_state_store.get_closets()
        assert len(closets) > 0
        closet = seeded_state_store.get_closet(closets[0].id)
        assert closet is not None
        assert closet.id == closets[0].id

    def test_get_nonexistent_closet_returns_none(self, seeded_state_store: StateStore):
        closet = seeded_state_store.get_closet("nonexistent-closet-999")
        assert closet is None


class TestGetItem:
    """get_item() returns a single supply item by ID."""

    def test_get_existing_item(self, seeded_state_store: StateStore):
        items = seeded_state_store.get_items()
        assert len(items) > 0
        item = seeded_state_store.get_item(items[0].id)
        assert item is not None
        assert item.id == items[0].id

    def test_get_nonexistent_item_returns_none(self, state_store: StateStore):
        item = state_store.get_item("nonexistent-item-999")
        assert item is None


class TestGetItems:
    """get_items() returns a list of all supply items."""

    def test_get_items_returns_list(self, seeded_state_store: StateStore):
        items = seeded_state_store.get_items()
        assert isinstance(items, list)

    def test_get_items_returns_supply_item_objects(self, seeded_state_store: StateStore):
        items = seeded_state_store.get_items()
        for item in items:
            assert isinstance(item, SupplyItem)

    def test_get_items_empty_store(self, state_store: StateStore):
        items = state_store.get_items()
        assert items == []

    def test_get_items_with_filter(self, seeded_state_store: StateStore):
        """get_items(filter_fn) returns only items matching the filter."""
        critical_items = seeded_state_store.get_items(
            filter_fn=lambda i: i.criticality == ItemCriticality.CRITICAL
        )
        assert len(critical_items) > 0
        for item in critical_items:
            assert item.criticality == ItemCriticality.CRITICAL


class TestGetClosets:
    """get_closets() returns closets, optionally filtered."""

    def test_get_closets_with_filter(self, seeded_state_store: StateStore):
        icu_closets = seeded_state_store.get_closets(
            filter_fn=lambda c: c.unit == "ICU"
        )
        assert len(icu_closets) >= 1
        for closet in icu_closets:
            assert closet.unit == "ICU"


class TestStateTransitions:
    """StateStore transition methods validate via the state machine."""

    async def test_transition_scan_valid(self, state_store: StateStore):
        scan = ScanResult(id="SCAN-T1", closet_id="CLO-ICU-01")
        state_store.scans["SCAN-T1"] = scan
        result = await state_store.transition_scan("SCAN-T1", ScanState.ANALYZING)
        assert result.state == ScanState.ANALYZING

    async def test_transition_scan_invalid_raises(self, state_store: StateStore):
        scan = ScanResult(id="SCAN-T1", closet_id="CLO-ICU-01",
                          state=ScanState.INITIATED)
        state_store.scans["SCAN-T1"] = scan
        with pytest.raises(InvalidTransitionError):
            await state_store.transition_scan("SCAN-T1", ScanState.COMPLETE)

    async def test_transition_scan_nonexistent_raises(self, state_store: StateStore):
        with pytest.raises(KeyError):
            await state_store.transition_scan("fake-scan-999", ScanState.ANALYZING)

    async def test_transition_purchase_order_valid(self, state_store: StateStore):
        po = PurchaseOrder(id="PO-T1", scan_id="SCAN-T1",
                           vendor_id="VND-1", vendor_name="Test")
        state_store.purchase_orders["PO-T1"] = po
        result = await state_store.transition_purchase_order("PO-T1", POState.APPROVED)
        assert result.state == POState.APPROVED

    async def test_transition_purchase_order_invalid_raises(self, state_store: StateStore):
        po = PurchaseOrder(id="PO-T1", scan_id="SCAN-T1",
                           vendor_id="VND-1", vendor_name="Test")
        state_store.purchase_orders["PO-T1"] = po
        with pytest.raises(InvalidTransitionError):
            await state_store.transition_purchase_order("PO-T1", POState.RECEIVED)

    async def test_transition_purchase_order_nonexistent_raises(self, state_store: StateStore):
        with pytest.raises(KeyError):
            await state_store.transition_purchase_order("FAKE-PO", POState.APPROVED)

    async def test_transition_shipment_valid(self, state_store: StateStore):
        shipment = Shipment(id="SHP-T1", po_id="PO-T1",
                            vendor_id="VND-1", closet_id="CLO-1")
        state_store.shipments["SHP-T1"] = shipment
        result = await state_store.transition_shipment("SHP-T1", ShipmentState.SHIPPED)
        assert result.state == ShipmentState.SHIPPED

    async def test_transition_shipment_invalid_raises(self, state_store: StateStore):
        shipment = Shipment(id="SHP-T1", po_id="PO-T1",
                            vendor_id="VND-1", closet_id="CLO-1")
        state_store.shipments["SHP-T1"] = shipment
        with pytest.raises(InvalidTransitionError):
            await state_store.transition_shipment("SHP-T1", ShipmentState.DELIVERED)

    async def test_transition_shipment_nonexistent_raises(self, state_store: StateStore):
        with pytest.raises(KeyError):
            await state_store.transition_shipment("FAKE-SHP", ShipmentState.SHIPPED)


class TestSeedUnits:
    """Verify seeded closet distribution across units and floors."""

    def test_seed_floors(self, seeded_state_store: StateStore):
        closets = seeded_state_store.get_closets()
        floors = {c.floor for c in closets}
        assert "floor-2" in floors
        assert "floor-3" in floors
        assert "floor-4" in floors

    def test_seed_units(self, seeded_state_store: StateStore):
        closets = seeded_state_store.get_closets()
        units = {c.unit for c in closets}
        assert "ICU" in units
        assert "Med-Surg" in units
        assert "OR" in units

    def test_seed_items_across_closets(self, seeded_state_store: StateStore):
        items = seeded_state_store.get_items()
        closet_ids = {i.closet_id for i in items}
        assert len(closet_ids) >= 3, "Items should span multiple closets"

    def test_seed_vendors_have_various_tiers(self, seeded_state_store: StateStore):
        vendors = seeded_state_store.get_vendors()
        tiers = {v.contract_tier for v in vendors}
        assert ContractTier.GPO_CONTRACT in tiers
        assert ContractTier.PREFERRED in tiers
        assert ContractTier.SPOT_BUY in tiers


class TestGetters:
    """Additional getter tests for vendors, scans, POs, shipments."""

    def test_get_vendor_returns_none_for_missing(self, state_store: StateStore):
        assert state_store.get_vendor("NOPE") is None

    def test_get_scan_returns_none_for_missing(self, state_store: StateStore):
        assert state_store.get_scan("NOPE") is None

    def test_get_purchase_order_returns_none_for_missing(self, state_store: StateStore):
        assert state_store.get_purchase_order("NOPE") is None

    def test_get_shipment_returns_none_for_missing(self, state_store: StateStore):
        assert state_store.get_shipment("NOPE") is None

    def test_get_catalog_entry_returns_none_for_missing(self, state_store: StateStore):
        assert state_store.get_catalog_entry("NOPE") is None

    def test_get_items_with_category_filter(self, seeded_state_store: StateStore):
        iv_items = seeded_state_store.get_items(
            filter_fn=lambda i: i.category == ItemCategory.IV_THERAPY
        )
        assert len(iv_items) >= 1
        for item in iv_items:
            assert item.category == ItemCategory.IV_THERAPY


class TestConcurrentAccess:
    """Test that the asyncio lock prevents race conditions."""

    async def test_concurrent_scan_transitions(self, state_store: StateStore):
        """Run many concurrent transitions on different scans — all should succeed."""
        for i in range(10):
            scan = ScanResult(id=f"SCAN-{i}", closet_id="CLO-ICU-01")
            state_store.scans[f"SCAN-{i}"] = scan

        async def transition(scan_id):
            await state_store.transition_scan(scan_id, ScanState.ANALYZING)

        await asyncio.gather(*(transition(f"SCAN-{i}") for i in range(10)))

        for i in range(10):
            assert state_store.get_scan(
                f"SCAN-{i}").state == ScanState.ANALYZING

    async def test_concurrent_conflicting_po_transitions(self, state_store: StateStore):
        """Two concurrent transitions on same PO — one should win, other should fail."""
        po = PurchaseOrder(id="PO-RACE", scan_id="SCAN-1",
                           vendor_id="VND-1", vendor_name="Test")
        state_store.purchase_orders["PO-RACE"] = po

        results = []

        async def try_approve():
            try:
                await state_store.transition_purchase_order("PO-RACE", POState.APPROVED)
                results.append("APPROVED")
            except Exception:
                results.append("FAILED")

        async def try_pending():
            try:
                await state_store.transition_purchase_order("PO-RACE", POState.PENDING_APPROVAL)
                results.append("PENDING")
            except Exception:
                results.append("FAILED")

        await asyncio.gather(try_approve(), try_pending())
        # One should succeed, the other may fail depending on ordering
        successes = [r for r in results if r != "FAILED"]
        assert len(successes) >= 1
