"""Pydantic v2 entity models for the supply-closet replenishment domain."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .enums import (
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupplyCloset(BaseModel):
    id: str
    name: str
    floor: str
    unit: str
    location: str


class SupplyItem(BaseModel):
    id: str
    sku: str
    name: str
    closet_id: str
    category: ItemCategory
    criticality: ItemCriticality
    par_level: int
    reorder_quantity: int
    current_quantity: int
    unit_of_measure: str
    consumption_rate_per_day: float
    last_restocked: datetime = Field(default_factory=_utcnow)


class Vendor(BaseModel):
    id: str
    name: str
    contract_tier: ContractTier
    lead_time_days: int
    expedite_lead_time_days: int
    minimum_order_value: float


class CatalogEntry(BaseModel):
    id: str
    vendor_id: str
    item_sku: str
    unit_price: float
    contract_tier: ContractTier
    stock_status: VendorStockStatus
    lead_time_days: int
    substitute_sku: Optional[str] = None


class POLineItem(BaseModel):
    item_sku: str
    item_name: str
    quantity: int
    unit_price: float
    extended_price: float
    contract_tier: ContractTier
    criticality: ItemCriticality


class PurchaseOrder(BaseModel):
    id: str
    scan_id: str
    vendor_id: str
    vendor_name: str
    state: POState = POState.CREATED
    approval_status: POApprovalStatus = POApprovalStatus.AUTO_APPROVED
    line_items: list[POLineItem] = Field(default_factory=list)
    total_cost: float = 0.0
    created_at: datetime = Field(default_factory=_utcnow)
    approved_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    requires_human_approval: bool = False
    approval_note: str = ""
    closet_id: str = ""


class ReorderItem(BaseModel):
    item_id: str
    item_sku: str
    item_name: str
    current_quantity: int
    par_level: int
    reorder_quantity: int
    criticality: ItemCriticality
    days_until_stockout: float
    recommended_vendor_id: Optional[str] = None
    recommended_unit_price: Optional[float] = None


class ScanResult(BaseModel):
    id: str
    closet_id: str
    state: ScanState = ScanState.INITIATED
    initiated_at: datetime = Field(default_factory=_utcnow)
    completed_at: Optional[datetime] = None
    items_scanned: int = 0
    items_below_par: int = 0
    items_to_reorder: list[ReorderItem] = Field(default_factory=list)
    purchase_order_ids: list[str] = Field(default_factory=list)


class Shipment(BaseModel):
    id: str
    po_id: str
    vendor_id: str
    closet_id: str
    state: ShipmentState = ShipmentState.CREATED
    carrier: str = ""
    tracking_number: Optional[str] = None
    expected_delivery: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    items_count: int = 0


class AgentMessage(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_name: str
    agent_role: str
    content: str
    intent_tag: IntentTag
    related_event_ids: list[str] = Field(default_factory=list)
