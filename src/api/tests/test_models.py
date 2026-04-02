"""
Entity model tests — creating entities, enum completeness, serialization, defaults.

These tests serve as a specification for the supply closet replenishment domain model.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone

from app.models.enums import (
    ContractTier,
    IntentTag,
    ItemCategory,
    ItemCriticality,
    POApprovalStatus,
    POState,
    ScanState,
    ShipmentState,
    TaskState,
    VendorStockStatus,
)
from app.models.entities import (
    AgentMessage,
    CatalogEntry,
    POLineItem,
    PurchaseOrder,
    ReorderItem,
    ScanResult,
    Shipment,
    SupplyCloset,
    SupplyItem,
    Vendor,
)


# ===================================================================
# Enum completeness — every expected state exists
# ===================================================================

class TestItemCategoryEnum:

    EXPECTED_VALUES = {
        "IV_THERAPY", "SURGICAL", "PPE", "WOUND_CARE",
        "CLEANING", "LINEN", "GENERAL", "SHARPS",
    }

    def test_all_expected_values_exist(self):
        actual = {s.value for s in ItemCategory}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(ItemCategory) == 8

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert ItemCategory(value).value == value


class TestItemCriticalityEnum:

    EXPECTED_VALUES = {"CRITICAL", "STANDARD", "LOW"}

    def test_all_expected_values_exist(self):
        actual = {s.value for s in ItemCriticality}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(ItemCriticality) == 3

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert ItemCriticality(value).value == value


class TestContractTierEnum:

    EXPECTED_VALUES = {"GPO_CONTRACT", "PREFERRED", "SPOT_BUY"}

    def test_all_expected_values_exist(self):
        actual = {s.value for s in ContractTier}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(ContractTier) == 3

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert ContractTier(value).value == value


class TestPOStateEnum:
    """POState must contain exactly the 8 states."""

    EXPECTED_VALUES = {
        "CREATED", "PENDING_APPROVAL", "APPROVED", "SUBMITTED",
        "CONFIRMED", "SHIPPED", "RECEIVED", "CANCELLED",
    }

    def test_all_expected_values_exist(self):
        actual = {s.value for s in POState}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(POState) == 8

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert POState(value).value == value


class TestPOApprovalStatusEnum:

    EXPECTED_VALUES = {"AUTO_APPROVED", "PENDING_HUMAN", "HUMAN_APPROVED", "HUMAN_REJECTED"}

    def test_all_expected_values_exist(self):
        actual = {s.value for s in POApprovalStatus}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(POApprovalStatus) == 4

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert POApprovalStatus(value).value == value


class TestScanStateEnum:
    """ScanState must contain exactly the 7 states."""

    EXPECTED_VALUES = {
        "INITIATED", "ANALYZING", "ITEMS_IDENTIFIED", "SOURCING",
        "ORDERING", "PENDING_APPROVAL", "COMPLETE",
    }

    def test_all_expected_values_exist(self):
        actual = {s.value for s in ScanState}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(ScanState) == 7

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert ScanState(value).value == value


class TestVendorStockStatusEnum:

    EXPECTED_VALUES = {"IN_STOCK", "LOW_STOCK", "OUT_OF_STOCK", "DISCONTINUED"}

    def test_all_expected_values_exist(self):
        actual = {s.value for s in VendorStockStatus}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(VendorStockStatus) == 4

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert VendorStockStatus(value).value == value


class TestShipmentStateEnum:
    """ShipmentState must contain exactly the 5 states."""

    EXPECTED_VALUES = {"CREATED", "SHIPPED", "IN_TRANSIT", "DELIVERED", "DELAYED"}

    def test_all_expected_values_exist(self):
        actual = {s.value for s in ShipmentState}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(ShipmentState) == 5

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert ShipmentState(value).value == value


class TestTaskStateEnum:
    """TaskState must contain exactly the 6 states (unchanged)."""

    EXPECTED_VALUES = {
        "CREATED", "ACCEPTED", "IN_PROGRESS",
        "COMPLETED", "ESCALATED", "CANCELLED",
    }

    def test_all_expected_values_exist(self):
        actual = {s.value for s in TaskState}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(TaskState) == 6

    @pytest.mark.parametrize("value", EXPECTED_VALUES)
    def test_each_value_accessible(self, value: str):
        assert TaskState(value).value == value


class TestIntentTagEnum:

    EXPECTED_VALUES = {"PROPOSE", "VALIDATE", "EXECUTE", "ESCALATE"}

    def test_all_expected_values_exist(self):
        actual = {t.value for t in IntentTag}
        assert self.EXPECTED_VALUES == actual

    def test_enum_count(self):
        assert len(IntentTag) == 4


# ===================================================================
# Entity creation — constructing each type with required fields
# ===================================================================

class TestSupplyClosetCreation:

    def test_create_closet_with_required_fields(self):
        closet = SupplyCloset(
            id="CLO-100", name="Test Closet", floor="floor-2",
            unit="ICU", location="2nd Floor, Wing A",
        )
        assert closet.id == "CLO-100"
        assert closet.name == "Test Closet"
        assert closet.floor == "floor-2"
        assert closet.unit == "ICU"
        assert closet.location == "2nd Floor, Wing A"


class TestSupplyItemCreation:

    def test_create_item_with_required_fields(self):
        item = SupplyItem(
            id="ITEM-100", sku="SKU-100", name="Test Item",
            closet_id="CLO-100", category=ItemCategory.PPE,
            criticality=ItemCriticality.STANDARD, par_level=50,
            reorder_quantity=100, current_quantity=30,
            unit_of_measure="each", consumption_rate_per_day=5.0,
        )
        assert item.id == "ITEM-100"
        assert item.sku == "SKU-100"
        assert item.closet_id == "CLO-100"
        assert item.category == ItemCategory.PPE
        assert item.criticality == ItemCriticality.STANDARD

    def test_item_has_par_level_and_reorder_quantity(self):
        item = SupplyItem(
            id="ITEM-100", sku="SKU-100", name="Test Item",
            closet_id="CLO-100", category=ItemCategory.IV_THERAPY,
            criticality=ItemCriticality.CRITICAL, par_level=50,
            reorder_quantity=100, current_quantity=12,
            unit_of_measure="bag", consumption_rate_per_day=8.0,
        )
        assert item.par_level == 50
        assert item.reorder_quantity == 100
        assert item.current_quantity == 12

    def test_item_consumption_rate(self):
        item = SupplyItem(
            id="ITEM-100", sku="SKU-100", name="Test Item",
            closet_id="CLO-100", category=ItemCategory.SURGICAL,
            criticality=ItemCriticality.CRITICAL, par_level=40,
            reorder_quantity=80, current_quantity=38,
            unit_of_measure="box", consumption_rate_per_day=3.0,
        )
        assert item.consumption_rate_per_day == 3.0

    def test_item_has_last_restocked_timestamp(self):
        item = SupplyItem(
            id="ITEM-100", sku="SKU-100", name="Test Item",
            closet_id="CLO-100", category=ItemCategory.PPE,
            criticality=ItemCriticality.STANDARD, par_level=50,
            reorder_quantity=100, current_quantity=30,
            unit_of_measure="each", consumption_rate_per_day=5.0,
        )
        assert isinstance(item.last_restocked, datetime)


class TestVendorCreation:

    def test_create_vendor_with_required_fields(self):
        vendor = Vendor(
            id="VND-100", name="Test Vendor",
            contract_tier=ContractTier.GPO_CONTRACT,
            lead_time_days=2, expedite_lead_time_days=1,
            minimum_order_value=500.0,
        )
        assert vendor.id == "VND-100"
        assert vendor.name == "Test Vendor"
        assert vendor.contract_tier == ContractTier.GPO_CONTRACT
        assert vendor.lead_time_days == 2
        assert vendor.expedite_lead_time_days == 1
        assert vendor.minimum_order_value == 500.0


class TestCatalogEntryCreation:

    def test_create_catalog_entry(self):
        entry = CatalogEntry(
            id="CAT-100", vendor_id="VND-100", item_sku="SKU-100",
            unit_price=3.50, contract_tier=ContractTier.GPO_CONTRACT,
            stock_status=VendorStockStatus.IN_STOCK, lead_time_days=2,
        )
        assert entry.id == "CAT-100"
        assert entry.vendor_id == "VND-100"
        assert entry.unit_price == 3.50
        assert entry.stock_status == VendorStockStatus.IN_STOCK

    def test_catalog_entry_substitute_defaults_none(self):
        entry = CatalogEntry(
            id="CAT-100", vendor_id="VND-100", item_sku="SKU-100",
            unit_price=3.50, contract_tier=ContractTier.GPO_CONTRACT,
            stock_status=VendorStockStatus.IN_STOCK, lead_time_days=2,
        )
        assert entry.substitute_sku is None

    def test_catalog_entry_with_substitute(self):
        entry = CatalogEntry(
            id="CAT-100", vendor_id="VND-100", item_sku="SKU-100",
            unit_price=3.50, contract_tier=ContractTier.GPO_CONTRACT,
            stock_status=VendorStockStatus.OUT_OF_STOCK, lead_time_days=2,
            substitute_sku="SKU-ALT",
        )
        assert entry.substitute_sku == "SKU-ALT"


class TestPurchaseOrderCreation:

    def test_create_po_with_required_fields(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
        )
        assert po.id == "PO-100"
        assert po.scan_id == "SCAN-100"
        assert po.vendor_id == "VND-100"

    def test_po_default_state_is_created(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
        )
        assert po.state == POState.CREATED

    def test_po_default_approval_status(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
        )
        assert po.approval_status == POApprovalStatus.AUTO_APPROVED

    def test_po_default_line_items_empty(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
        )
        assert po.line_items == []

    def test_po_default_total_cost_zero(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
        )
        assert po.total_cost == 0.0

    def test_po_with_line_items(self):
        items = [
            POLineItem(
                item_sku="NS-1000ML", item_name="Normal Saline",
                quantity=100, unit_price=3.50, extended_price=350.0,
                contract_tier=ContractTier.GPO_CONTRACT,
                criticality=ItemCriticality.CRITICAL,
            ),
        ]
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
            line_items=items, total_cost=350.0,
        )
        assert len(po.line_items) == 1
        assert po.line_items[0].item_sku == "NS-1000ML"
        assert po.total_cost == 350.0

    def test_po_requires_human_approval_defaults_false(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
        )
        assert po.requires_human_approval is False

    def test_po_has_created_at_timestamp(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
        )
        assert isinstance(po.created_at, datetime)


class TestScanResultCreation:

    def test_create_scan_with_required_fields(self):
        scan = ScanResult(id="SCAN-100", closet_id="CLO-100")
        assert scan.id == "SCAN-100"
        assert scan.closet_id == "CLO-100"

    def test_scan_default_state_is_initiated(self):
        scan = ScanResult(id="SCAN-100", closet_id="CLO-100")
        assert scan.state == ScanState.INITIATED

    def test_scan_default_counts_zero(self):
        scan = ScanResult(id="SCAN-100", closet_id="CLO-100")
        assert scan.items_scanned == 0
        assert scan.items_below_par == 0

    def test_scan_default_reorder_items_empty(self):
        scan = ScanResult(id="SCAN-100", closet_id="CLO-100")
        assert scan.items_to_reorder == []

    def test_scan_default_po_ids_empty(self):
        scan = ScanResult(id="SCAN-100", closet_id="CLO-100")
        assert scan.purchase_order_ids == []

    def test_scan_has_initiated_at_timestamp(self):
        scan = ScanResult(id="SCAN-100", closet_id="CLO-100")
        assert isinstance(scan.initiated_at, datetime)

    def test_scan_completed_at_defaults_none(self):
        scan = ScanResult(id="SCAN-100", closet_id="CLO-100")
        assert scan.completed_at is None


class TestShipmentCreation:

    def test_create_shipment_with_required_fields(self):
        shipment = Shipment(
            id="SHP-100", po_id="PO-100",
            vendor_id="VND-100", closet_id="CLO-100",
        )
        assert shipment.id == "SHP-100"
        assert shipment.po_id == "PO-100"
        assert shipment.vendor_id == "VND-100"
        assert shipment.closet_id == "CLO-100"

    def test_shipment_default_state_is_created(self):
        shipment = Shipment(
            id="SHP-100", po_id="PO-100",
            vendor_id="VND-100", closet_id="CLO-100",
        )
        assert shipment.state == ShipmentState.CREATED

    def test_shipment_default_carrier_empty(self):
        shipment = Shipment(
            id="SHP-100", po_id="PO-100",
            vendor_id="VND-100", closet_id="CLO-100",
        )
        assert shipment.carrier == ""

    def test_shipment_tracking_defaults_none(self):
        shipment = Shipment(
            id="SHP-100", po_id="PO-100",
            vendor_id="VND-100", closet_id="CLO-100",
        )
        assert shipment.tracking_number is None

    def test_shipment_delivered_at_defaults_none(self):
        shipment = Shipment(
            id="SHP-100", po_id="PO-100",
            vendor_id="VND-100", closet_id="CLO-100",
        )
        assert shipment.delivered_at is None

    def test_shipment_default_items_count_zero(self):
        shipment = Shipment(
            id="SHP-100", po_id="PO-100",
            vendor_id="VND-100", closet_id="CLO-100",
        )
        assert shipment.items_count == 0


class TestReorderItemCreation:

    def test_create_reorder_item(self):
        ri = ReorderItem(
            item_id="ITEM-100", item_sku="SKU-100", item_name="Test Item",
            current_quantity=12, par_level=50, reorder_quantity=100,
            criticality=ItemCriticality.CRITICAL, days_until_stockout=1.5,
        )
        assert ri.item_id == "ITEM-100"
        assert ri.days_until_stockout == 1.5

    def test_reorder_item_optional_vendor_defaults_none(self):
        ri = ReorderItem(
            item_id="ITEM-100", item_sku="SKU-100", item_name="Test Item",
            current_quantity=12, par_level=50, reorder_quantity=100,
            criticality=ItemCriticality.CRITICAL, days_until_stockout=1.5,
        )
        assert ri.recommended_vendor_id is None
        assert ri.recommended_unit_price is None


class TestAgentMessageCreation:

    def test_create_agent_message(self):
        msg = AgentMessage(
            id="msg-001",
            agent_name="SupplyCoordinator",
            agent_role="coordinator",
            content="Analyzing inventory options.",
            intent_tag=IntentTag.PROPOSE,
        )
        assert msg.id == "msg-001"
        assert msg.agent_name == "SupplyCoordinator"
        assert msg.intent_tag == IntentTag.PROPOSE

    def test_agent_message_default_related_events_empty(self):
        msg = AgentMessage(
            id="msg-001",
            agent_name="SupplyCoordinator",
            agent_role="coordinator",
            content="Test",
            intent_tag=IntentTag.EXECUTE,
        )
        assert msg.related_event_ids == []


# ===================================================================
# Serialization / deserialization — Pydantic model_dump / model_validate
# ===================================================================

class TestSupplyClosetSerialization:

    def test_closet_round_trips_through_dict(self):
        closet = SupplyCloset(
            id="CLO-100", name="Test Closet", floor="floor-2",
            unit="ICU", location="2nd Floor",
        )
        data = closet.model_dump()
        restored = SupplyCloset.model_validate(data)
        assert restored == closet

    def test_closet_round_trips_through_json(self):
        closet = SupplyCloset(
            id="CLO-100", name="Test Closet", floor="floor-2",
            unit="ICU", location="2nd Floor",
        )
        json_str = closet.model_dump_json()
        restored = SupplyCloset.model_validate_json(json_str)
        assert restored == closet


class TestSupplyItemSerialization:

    def test_item_round_trips_through_dict(self):
        item = SupplyItem(
            id="ITEM-100", sku="SKU-100", name="Test Item",
            closet_id="CLO-100", category=ItemCategory.PPE,
            criticality=ItemCriticality.STANDARD, par_level=50,
            reorder_quantity=100, current_quantity=30,
            unit_of_measure="each", consumption_rate_per_day=5.0,
        )
        data = item.model_dump()
        restored = SupplyItem.model_validate(data)
        assert restored == item

    def test_item_round_trips_through_json(self):
        item = SupplyItem(
            id="ITEM-100", sku="SKU-100", name="Test Item",
            closet_id="CLO-100", category=ItemCategory.IV_THERAPY,
            criticality=ItemCriticality.CRITICAL, par_level=50,
            reorder_quantity=100, current_quantity=12,
            unit_of_measure="bag", consumption_rate_per_day=8.0,
        )
        json_str = item.model_dump_json()
        restored = SupplyItem.model_validate_json(json_str)
        assert restored == item

    def test_item_dict_has_expected_keys(self):
        item = SupplyItem(
            id="ITEM-100", sku="SKU-100", name="Test Item",
            closet_id="CLO-100", category=ItemCategory.PPE,
            criticality=ItemCriticality.STANDARD, par_level=50,
            reorder_quantity=100, current_quantity=30,
            unit_of_measure="each", consumption_rate_per_day=5.0,
        )
        data = item.model_dump()
        assert "id" in data
        assert "sku" in data
        assert "closet_id" in data
        assert "category" in data
        assert "criticality" in data
        assert "par_level" in data
        assert "current_quantity" in data


class TestPurchaseOrderSerialization:

    def test_po_round_trips_through_dict(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
            state=POState.APPROVED,
            line_items=[POLineItem(
                item_sku="NS-1000ML", item_name="Normal Saline",
                quantity=100, unit_price=3.50, extended_price=350.0,
                contract_tier=ContractTier.GPO_CONTRACT,
                criticality=ItemCriticality.CRITICAL,
            )],
            total_cost=350.0,
        )
        data = po.model_dump()
        restored = PurchaseOrder.model_validate(data)
        assert restored == po

    def test_po_round_trips_through_json(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
        )
        json_str = po.model_dump_json()
        restored = PurchaseOrder.model_validate_json(json_str)
        assert restored == po

    def test_po_line_items_included_in_serialization(self):
        po = PurchaseOrder(
            id="PO-100", scan_id="SCAN-100",
            vendor_id="VND-100", vendor_name="Test Vendor",
            line_items=[POLineItem(
                item_sku="NS-1000ML", item_name="Normal Saline",
                quantity=100, unit_price=3.50, extended_price=350.0,
                contract_tier=ContractTier.GPO_CONTRACT,
                criticality=ItemCriticality.CRITICAL,
            )],
        )
        data = po.model_dump()
        assert len(data["line_items"]) == 1
        assert data["line_items"][0]["item_sku"] == "NS-1000ML"


class TestShipmentSerialization:

    def test_shipment_round_trips_through_dict(self):
        shipment = Shipment(
            id="SHP-100", po_id="PO-100",
            vendor_id="VND-100", closet_id="CLO-100",
            state=ShipmentState.IN_TRANSIT, carrier="MedExpress",
        )
        data = shipment.model_dump()
        restored = Shipment.model_validate(data)
        assert restored == shipment

    def test_shipment_round_trips_through_json(self):
        shipment = Shipment(
            id="SHP-100", po_id="PO-100",
            vendor_id="VND-100", closet_id="CLO-100",
        )
        json_str = shipment.model_dump_json()
        restored = Shipment.model_validate_json(json_str)
        assert restored == shipment
