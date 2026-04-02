"""In-memory state store with transition validation and seed data for the supply-closet replenishment domain."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from ..models.entities import (
    CatalogEntry,
    PurchaseOrder,
    ScanResult,
    Shipment,
    SupplyCloset,
    SupplyItem,
    Vendor,
)
from ..models.enums import (
    ContractTier,
    ItemCategory,
    ItemCriticality,
    POState,
    ScanState,
    ShipmentState,
    TaskState,
    VendorStockStatus,
)
from ..models.transitions import (
    VALID_PO_TRANSITIONS,
    VALID_SCAN_TRANSITIONS,
    VALID_SHIPMENT_TRANSITIONS,
    VALID_TASK_TRANSITIONS,
    validate_transition,
)


# ── Hospital configuration (floors, units, closets) ─────────────────

HOSPITAL_CONFIG: dict[str, Any] = {
    "floors": {
        "floor-2": {
            "id": "floor-2",
            "name": "Second Floor",
            "units": ["ICU", "NICU"],
        },
        "floor-3": {
            "id": "floor-3",
            "name": "Third Floor",
            "units": ["Med-Surg", "Oncology"],
        },
        "floor-4": {
            "id": "floor-4",
            "name": "Fourth Floor",
            "units": ["OR", "PACU"],
        },
    },
}


class StateStore:
    """Authoritative in-memory state for closets, supply items, vendors, catalog,
    scans, purchase orders, and shipments.

    All mutations acquire ``_lock`` and run state-machine validation via
    ``transitions.validate_transition`` before changing entity state.
    """

    def __init__(self) -> None:
        self.closets: dict[str, SupplyCloset] = {}
        self.items: dict[str, SupplyItem] = {}
        self.vendors: dict[str, Vendor] = {}
        self.catalog: dict[str, CatalogEntry] = {}
        self.scans: dict[str, ScanResult] = {}
        self.purchase_orders: dict[str, PurchaseOrder] = {}
        self.shipments: dict[str, Shipment] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    # ── Getters ─────────────────────────────────────────────────────

    def get_closet(self, closet_id: str) -> Optional[SupplyCloset]:
        return self.closets.get(closet_id)

    def get_item(self, item_id: str) -> Optional[SupplyItem]:
        return self.items.get(item_id)

    def get_vendor(self, vendor_id: str) -> Optional[Vendor]:
        return self.vendors.get(vendor_id)

    def get_catalog_entry(self, entry_id: str) -> Optional[CatalogEntry]:
        return self.catalog.get(entry_id)

    def get_scan(self, scan_id: str) -> Optional[ScanResult]:
        return self.scans.get(scan_id)

    def get_purchase_order(self, po_id: str) -> Optional[PurchaseOrder]:
        return self.purchase_orders.get(po_id)

    def get_shipment(self, shipment_id: str) -> Optional[Shipment]:
        return self.shipments.get(shipment_id)

    def get_closets(
        self, filter_fn: Optional[Callable[[SupplyCloset], bool]] = None
    ) -> list[SupplyCloset]:
        closets = list(self.closets.values())
        if filter_fn:
            closets = [c for c in closets if filter_fn(c)]
        return closets

    def get_items(
        self, filter_fn: Optional[Callable[[SupplyItem], bool]] = None
    ) -> list[SupplyItem]:
        items = list(self.items.values())
        if filter_fn:
            items = [i for i in items if filter_fn(i)]
        return items

    def get_vendors(
        self, filter_fn: Optional[Callable[[Vendor], bool]] = None
    ) -> list[Vendor]:
        vendors = list(self.vendors.values())
        if filter_fn:
            vendors = [v for v in vendors if filter_fn(v)]
        return vendors

    def get_scans(
        self, filter_fn: Optional[Callable[[ScanResult], bool]] = None
    ) -> list[ScanResult]:
        scans = list(self.scans.values())
        if filter_fn:
            scans = [s for s in scans if filter_fn(s)]
        return scans

    def get_purchase_orders(
        self, filter_fn: Optional[Callable[[PurchaseOrder], bool]] = None
    ) -> list[PurchaseOrder]:
        pos = list(self.purchase_orders.values())
        if filter_fn:
            pos = [p for p in pos if filter_fn(p)]
        return pos

    def get_shipments(
        self, filter_fn: Optional[Callable[[Shipment], bool]] = None
    ) -> list[Shipment]:
        shipments = list(self.shipments.values())
        if filter_fn:
            shipments = [s for s in shipments if filter_fn(s)]
        return shipments

    # ── State-transition helpers ────────────────────────────────────

    async def transition_scan(
        self, scan_id: str, new_state: ScanState
    ) -> ScanResult:
        async with self._lock:
            scan = self.scans.get(scan_id)
            if scan is None:
                raise KeyError(f"Scan {scan_id} not found")
            validate_transition(scan.state, new_state, VALID_SCAN_TRANSITIONS)
            scan.state = new_state
            return scan

    async def transition_purchase_order(
        self, po_id: str, new_state: POState
    ) -> PurchaseOrder:
        async with self._lock:
            po = self.purchase_orders.get(po_id)
            if po is None:
                raise KeyError(f"PurchaseOrder {po_id} not found")
            validate_transition(po.state, new_state, VALID_PO_TRANSITIONS)
            po.state = new_state
            return po

    async def transition_shipment(
        self, shipment_id: str, new_state: ShipmentState
    ) -> Shipment:
        async with self._lock:
            shipment = self.shipments.get(shipment_id)
            if shipment is None:
                raise KeyError(f"Shipment {shipment_id} not found")
            validate_transition(
                shipment.state, new_state, VALID_SHIPMENT_TRANSITIONS
            )
            shipment.state = new_state
            return shipment

    # ── Seed data ───────────────────────────────────────────────────

    def seed_initial_state(self) -> None:
        """Populate a realistic hospital supply-closet starting state.

        Creates closets, supply items, vendors, and catalog entries for
        demo purposes.
        """
        now = datetime.now(timezone.utc)

        # ── Closets ─────────────────────────────────────────────────
        closet_configs = [
            {"id": "CLO-ICU-01", "name": "ICU Main Closet", "floor": "floor-2",
                "unit": "ICU", "location": "2nd Floor, Wing A"},
            {"id": "CLO-NICU-01", "name": "NICU Closet", "floor": "floor-2",
                "unit": "NICU", "location": "2nd Floor, Wing B"},
            {"id": "CLO-SURG-01", "name": "Med-Surg Closet", "floor": "floor-3",
                "unit": "Med-Surg", "location": "3rd Floor, Wing A"},
            {"id": "CLO-ONC-01", "name": "Oncology Closet", "floor": "floor-3",
                "unit": "Oncology", "location": "3rd Floor, Wing B"},
            {"id": "CLO-OR-01", "name": "OR Supply Room", "floor": "floor-4",
                "unit": "OR", "location": "4th Floor, Suite 1"},
        ]
        for cfg in closet_configs:
            self.closets[cfg["id"]] = SupplyCloset(**cfg)

        # ── Supply items ────────────────────────────────────────────
        item_configs = [
            {"id": "ITEM-NS-ICU", "sku": "NS-1000ML", "name": "Normal Saline 1000mL", "closet_id": "CLO-ICU-01", "category": ItemCategory.IV_THERAPY, "criticality": ItemCriticality.CRITICAL,
                "par_level": 50, "reorder_quantity": 100, "current_quantity": 12, "unit_of_measure": "bag", "consumption_rate_per_day": 8.0, "last_restocked": now - timedelta(days=3)},
            {"id": "ITEM-GLV-ICU", "sku": "GLV-NITRILE-M", "name": "Nitrile Gloves Medium", "closet_id": "CLO-ICU-01", "category": ItemCategory.PPE, "criticality": ItemCriticality.STANDARD,
                "par_level": 200, "reorder_quantity": 500, "current_quantity": 180, "unit_of_measure": "box", "consumption_rate_per_day": 15.0, "last_restocked": now - timedelta(days=1)},
            {"id": "ITEM-SYRINGE-ICU", "sku": "SYR-10ML", "name": "Syringe 10mL", "closet_id": "CLO-ICU-01", "category": ItemCategory.IV_THERAPY, "criticality": ItemCriticality.CRITICAL,
                "par_level": 100, "reorder_quantity": 200, "current_quantity": 95, "unit_of_measure": "each", "consumption_rate_per_day": 12.0, "last_restocked": now - timedelta(days=2)},
            {"id": "ITEM-GOWN-SURG", "sku": "GOWN-STERILE-L", "name": "Sterile Gown Large", "closet_id": "CLO-SURG-01", "category": ItemCategory.SURGICAL, "criticality": ItemCriticality.CRITICAL,
                "par_level": 30, "reorder_quantity": 60, "current_quantity": 8, "unit_of_measure": "each", "consumption_rate_per_day": 4.0, "last_restocked": now - timedelta(days=5)},
            {"id": "ITEM-GAUZE-SURG", "sku": "GAUZE-4X4", "name": "Gauze Pads 4x4", "closet_id": "CLO-SURG-01", "category": ItemCategory.WOUND_CARE, "criticality": ItemCriticality.STANDARD,
                "par_level": 100, "reorder_quantity": 200, "current_quantity": 45, "unit_of_measure": "pack", "consumption_rate_per_day": 10.0, "last_restocked": now - timedelta(days=4)},
            {"id": "ITEM-SUTURE-OR", "sku": "SUTURE-VICRYL", "name": "Vicryl Sutures 3-0", "closet_id": "CLO-OR-01", "category": ItemCategory.SURGICAL, "criticality": ItemCriticality.CRITICAL,
                "par_level": 40, "reorder_quantity": 80, "current_quantity": 38, "unit_of_measure": "box", "consumption_rate_per_day": 3.0, "last_restocked": now - timedelta(days=2)},
            {"id": "ITEM-SHARPS-OR", "sku": "SHARPS-CONT-1G", "name": "Sharps Container 1gal", "closet_id": "CLO-OR-01", "category": ItemCategory.SHARPS, "criticality": ItemCriticality.STANDARD,
                "par_level": 20, "reorder_quantity": 40, "current_quantity": 5, "unit_of_measure": "each", "consumption_rate_per_day": 2.0, "last_restocked": now - timedelta(days=7)},
            {"id": "ITEM-MASK-NICU", "sku": "MASK-N95", "name": "N95 Respirator", "closet_id": "CLO-NICU-01", "category": ItemCategory.PPE, "criticality": ItemCriticality.CRITICAL,
                "par_level": 80, "reorder_quantity": 160, "current_quantity": 75, "unit_of_measure": "each", "consumption_rate_per_day": 6.0, "last_restocked": now - timedelta(days=1)},
            {"id": "ITEM-BLEACH-ONC", "sku": "BLEACH-WIPE-160", "name": "Bleach Disinfectant Wipes", "closet_id": "CLO-ONC-01", "category": ItemCategory.CLEANING, "criticality": ItemCriticality.LOW,
                "par_level": 24, "reorder_quantity": 48, "current_quantity": 22, "unit_of_measure": "canister", "consumption_rate_per_day": 2.0, "last_restocked": now - timedelta(days=3)},
            {"id": "ITEM-LINEN-SURG", "sku": "LINEN-SHEET-STD", "name": "Standard Bed Sheet", "closet_id": "CLO-SURG-01", "category": ItemCategory.LINEN, "criticality": ItemCriticality.LOW,
                "par_level": 40, "reorder_quantity": 80, "current_quantity": 35, "unit_of_measure": "each", "consumption_rate_per_day": 5.0, "last_restocked": now - timedelta(days=2)},
        ]
        for cfg in item_configs:
            self.items[cfg["id"]] = SupplyItem(**cfg)

        # ── Vendors ─────────────────────────────────────────────────
        vendor_configs = [
            {"id": "VND-MEDLINE", "name": "Medline Industries", "contract_tier": ContractTier.GPO_CONTRACT,
                "lead_time_days": 2, "expedite_lead_time_days": 1, "minimum_order_value": 500.0},
            {"id": "VND-CARDINAL", "name": "Cardinal Health", "contract_tier": ContractTier.GPO_CONTRACT,
                "lead_time_days": 3, "expedite_lead_time_days": 1, "minimum_order_value": 750.0},
            {"id": "VND-MCKESSON", "name": "McKesson Medical", "contract_tier": ContractTier.PREFERRED,
                "lead_time_days": 2, "expedite_lead_time_days": 1, "minimum_order_value": 300.0},
            {"id": "VND-SPOTMED", "name": "SpotMed Supplies", "contract_tier": ContractTier.SPOT_BUY,
                "lead_time_days": 5, "expedite_lead_time_days": 2, "minimum_order_value": 100.0},
        ]
        for cfg in vendor_configs:
            self.vendors[cfg["id"]] = Vendor(**cfg)

        # ── Catalog entries ─────────────────────────────────────────
        catalog_configs = [
            {"id": "CAT-NS-MED", "vendor_id": "VND-MEDLINE", "item_sku": "NS-1000ML", "unit_price": 3.50,
                "contract_tier": ContractTier.GPO_CONTRACT, "stock_status": VendorStockStatus.IN_STOCK, "lead_time_days": 2},
            {"id": "CAT-NS-CARD", "vendor_id": "VND-CARDINAL", "item_sku": "NS-1000ML", "unit_price": 3.75,
                "contract_tier": ContractTier.GPO_CONTRACT, "stock_status": VendorStockStatus.IN_STOCK, "lead_time_days": 3},
            {"id": "CAT-GLV-MED", "vendor_id": "VND-MEDLINE", "item_sku": "GLV-NITRILE-M", "unit_price": 12.00,
                "contract_tier": ContractTier.GPO_CONTRACT, "stock_status": VendorStockStatus.IN_STOCK, "lead_time_days": 2},
            {"id": "CAT-GOWN-CARD", "vendor_id": "VND-CARDINAL", "item_sku": "GOWN-STERILE-L", "unit_price": 8.50,
                "contract_tier": ContractTier.GPO_CONTRACT, "stock_status": VendorStockStatus.LOW_STOCK, "lead_time_days": 3},
            {"id": "CAT-GOWN-SPOT", "vendor_id": "VND-SPOTMED", "item_sku": "GOWN-STERILE-L", "unit_price": 14.00,
                "contract_tier": ContractTier.SPOT_BUY, "stock_status": VendorStockStatus.IN_STOCK, "lead_time_days": 5},
            {"id": "CAT-GAUZE-MCK", "vendor_id": "VND-MCKESSON", "item_sku": "GAUZE-4X4", "unit_price": 4.25,
                "contract_tier": ContractTier.PREFERRED, "stock_status": VendorStockStatus.IN_STOCK, "lead_time_days": 2},
            {"id": "CAT-SUTURE-CARD", "vendor_id": "VND-CARDINAL", "item_sku": "SUTURE-VICRYL", "unit_price": 45.00,
                "contract_tier": ContractTier.GPO_CONTRACT, "stock_status": VendorStockStatus.IN_STOCK, "lead_time_days": 3},
            {"id": "CAT-SHARPS-MCK", "vendor_id": "VND-MCKESSON", "item_sku": "SHARPS-CONT-1G", "unit_price": 6.75,
                "contract_tier": ContractTier.PREFERRED, "stock_status": VendorStockStatus.IN_STOCK, "lead_time_days": 2},
            {"id": "CAT-MASK-MED", "vendor_id": "VND-MEDLINE", "item_sku": "MASK-N95", "unit_price": 2.50,
                "contract_tier": ContractTier.GPO_CONTRACT, "stock_status": VendorStockStatus.IN_STOCK, "lead_time_days": 2},
        ]
        for cfg in catalog_configs:
            self.catalog[cfg["id"]] = CatalogEntry(**cfg)

    # ── Snapshot ────────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """Return all state as a serializable dict for ``GET /api/state``."""
        return {
            "closets": {k: v.model_dump(mode="json") for k, v in self.closets.items()},
            "items": {k: v.model_dump(mode="json") for k, v in self.items.items()},
            "vendors": {k: v.model_dump(mode="json") for k, v in self.vendors.items()},
            "catalog": {k: v.model_dump(mode="json") for k, v in self.catalog.items()},
            "scans": {k: v.model_dump(mode="json") for k, v in self.scans.items()},
            "purchase_orders": {k: v.model_dump(mode="json") for k, v in self.purchase_orders.items()},
            "shipments": {k: v.model_dump(mode="json") for k, v in self.shipments.items()},
            "hospital_config": HOSPITAL_CONFIG,
        }

    # ── Lifecycle ───────────────────────────────────────────────────

    def clear(self) -> None:
        """Wipe all state for a scenario reset."""
        self.closets.clear()
        self.items.clear()
        self.vendors.clear()
        self.catalog.clear()
        self.scans.clear()
        self.purchase_orders.clear()
        self.shipments.clear()
