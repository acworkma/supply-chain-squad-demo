"""
Shared test fixtures for the supply-closet replenishment API test suite.

These fixtures depend on domain models from app.models and stores from
app.events.event_store / app.state.store / app.messages.message_store.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.models.enums import (
    ContractTier,
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
from app.events.event_store import EventStore
from app.messages.message_store import MessageStore
from app.metrics.metrics_store import MetricsStore
from app.state.store import StateStore


# ---------------------------------------------------------------------------
# Store fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_store() -> EventStore:
    """Fresh event store — cleared after each test."""
    store = EventStore()
    yield store
    store.clear()


@pytest.fixture
def state_store() -> StateStore:
    """Fresh state store — cleared after each test."""
    store = StateStore()
    yield store
    store.clear()


@pytest.fixture
def message_store() -> MessageStore:
    """Fresh message store — cleared after each test."""
    store = MessageStore()
    yield store
    store.clear()


@pytest.fixture
def metrics_store() -> MetricsStore:
    """Fresh metrics store — cleared after each test."""
    store = MetricsStore()
    yield store
    store.clear()


@pytest.fixture
def seeded_state_store(state_store: StateStore) -> StateStore:
    """State store pre-seeded with the closet replenishment layout."""
    state_store.seed_initial_state()
    return state_store


# ---------------------------------------------------------------------------
# Sample entity fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_closets() -> list[SupplyCloset]:
    """Five closets across three floors."""
    return [
        SupplyCloset(id="CLO-ICU-01", name="ICU Main Closet",
                     floor="floor-2", unit="ICU", location="2nd Floor, Wing A"),
        SupplyCloset(id="CLO-NICU-01", name="NICU Closet",
                     floor="floor-2", unit="NICU", location="2nd Floor, Wing B"),
        SupplyCloset(id="CLO-SURG-01", name="Med-Surg Closet",
                     floor="floor-3", unit="Med-Surg", location="3rd Floor, Wing A"),
        SupplyCloset(id="CLO-ONC-01", name="Oncology Closet",
                     floor="floor-3", unit="Oncology", location="3rd Floor, Wing B"),
        SupplyCloset(id="CLO-OR-01", name="OR Supply Room",
                     floor="floor-4", unit="OR", location="4th Floor, Suite 1"),
    ]


@pytest.fixture
def sample_items() -> list[SupplyItem]:
    """Ten supply items across multiple closets, categories, and criticality levels."""
    now = datetime.now(timezone.utc)
    return [
        SupplyItem(id="ITEM-NS-ICU", sku="NS-1000ML", name="Normal Saline 1000mL", closet_id="CLO-ICU-01", category=ItemCategory.IV_THERAPY, criticality=ItemCriticality.CRITICAL,
                   par_level=50, reorder_quantity=100, current_quantity=12, unit_of_measure="bag", consumption_rate_per_day=8.0, last_restocked=now - timedelta(days=3)),
        SupplyItem(id="ITEM-GLV-ICU", sku="GLV-NITRILE-M", name="Nitrile Gloves Medium", closet_id="CLO-ICU-01", category=ItemCategory.PPE, criticality=ItemCriticality.STANDARD,
                   par_level=200, reorder_quantity=500, current_quantity=180, unit_of_measure="box", consumption_rate_per_day=15.0, last_restocked=now - timedelta(days=1)),
        SupplyItem(id="ITEM-SYRINGE-ICU", sku="SYR-10ML", name="Syringe 10mL", closet_id="CLO-ICU-01", category=ItemCategory.IV_THERAPY, criticality=ItemCriticality.CRITICAL,
                   par_level=100, reorder_quantity=200, current_quantity=95, unit_of_measure="each", consumption_rate_per_day=12.0, last_restocked=now - timedelta(days=2)),
        SupplyItem(id="ITEM-GOWN-SURG", sku="GOWN-STERILE-L", name="Sterile Gown Large", closet_id="CLO-SURG-01", category=ItemCategory.SURGICAL, criticality=ItemCriticality.CRITICAL,
                   par_level=30, reorder_quantity=60, current_quantity=8, unit_of_measure="each", consumption_rate_per_day=4.0, last_restocked=now - timedelta(days=5)),
        SupplyItem(id="ITEM-GAUZE-SURG", sku="GAUZE-4X4", name="Gauze Pads 4x4", closet_id="CLO-SURG-01", category=ItemCategory.WOUND_CARE, criticality=ItemCriticality.STANDARD,
                   par_level=100, reorder_quantity=200, current_quantity=45, unit_of_measure="pack", consumption_rate_per_day=10.0, last_restocked=now - timedelta(days=4)),
        SupplyItem(id="ITEM-SUTURE-OR", sku="SUTURE-VICRYL", name="Vicryl Sutures 3-0", closet_id="CLO-OR-01", category=ItemCategory.SURGICAL, criticality=ItemCriticality.CRITICAL,
                   par_level=40, reorder_quantity=80, current_quantity=38, unit_of_measure="box", consumption_rate_per_day=3.0, last_restocked=now - timedelta(days=2)),
        SupplyItem(id="ITEM-SHARPS-OR", sku="SHARPS-CONT-1G", name="Sharps Container 1gal", closet_id="CLO-OR-01", category=ItemCategory.SHARPS, criticality=ItemCriticality.STANDARD,
                   par_level=20, reorder_quantity=40, current_quantity=5, unit_of_measure="each", consumption_rate_per_day=2.0, last_restocked=now - timedelta(days=7)),
        SupplyItem(id="ITEM-MASK-NICU", sku="MASK-N95", name="N95 Respirator", closet_id="CLO-NICU-01", category=ItemCategory.PPE, criticality=ItemCriticality.CRITICAL,
                   par_level=80, reorder_quantity=160, current_quantity=75, unit_of_measure="each", consumption_rate_per_day=6.0, last_restocked=now - timedelta(days=1)),
        SupplyItem(id="ITEM-BLEACH-ONC", sku="BLEACH-WIPE-160", name="Bleach Disinfectant Wipes", closet_id="CLO-ONC-01", category=ItemCategory.CLEANING, criticality=ItemCriticality.LOW,
                   par_level=24, reorder_quantity=48, current_quantity=22, unit_of_measure="canister", consumption_rate_per_day=2.0, last_restocked=now - timedelta(days=3)),
        SupplyItem(id="ITEM-LINEN-SURG", sku="LINEN-SHEET-STD", name="Standard Bed Sheet", closet_id="CLO-SURG-01", category=ItemCategory.LINEN, criticality=ItemCriticality.LOW,
                   par_level=40, reorder_quantity=80, current_quantity=35, unit_of_measure="each", consumption_rate_per_day=5.0, last_restocked=now - timedelta(days=2)),
    ]


@pytest.fixture
def sample_vendors() -> list[Vendor]:
    """Four vendors at different contract tiers."""
    return [
        Vendor(id="VND-MEDLINE", name="Medline Industries", contract_tier=ContractTier.GPO_CONTRACT,
               lead_time_days=2, expedite_lead_time_days=1, minimum_order_value=500.0),
        Vendor(id="VND-CARDINAL", name="Cardinal Health", contract_tier=ContractTier.GPO_CONTRACT,
               lead_time_days=3, expedite_lead_time_days=1, minimum_order_value=750.0),
        Vendor(id="VND-MCKESSON", name="McKesson Medical", contract_tier=ContractTier.PREFERRED,
               lead_time_days=2, expedite_lead_time_days=1, minimum_order_value=300.0),
        Vendor(id="VND-SPOTMED", name="SpotMed Supplies", contract_tier=ContractTier.SPOT_BUY,
               lead_time_days=5, expedite_lead_time_days=2, minimum_order_value=100.0),
    ]


@pytest.fixture
def sample_scans() -> list[ScanResult]:
    """Scans in various states."""
    return [
        ScanResult(id="SCAN-001", closet_id="CLO-ICU-01",
                   state=ScanState.COMPLETE, items_scanned=10, items_below_par=3),
        ScanResult(id="SCAN-002", closet_id="CLO-SURG-01",
                   state=ScanState.ANALYZING, items_scanned=0, items_below_par=0),
        ScanResult(id="SCAN-003", closet_id="CLO-OR-01",
                   state=ScanState.INITIATED),
    ]


@pytest.fixture
def sample_purchase_orders() -> list[PurchaseOrder]:
    """Purchase orders at various stages."""
    return [
        PurchaseOrder(
            id="PO-001", scan_id="SCAN-001", vendor_id="VND-MEDLINE", vendor_name="Medline Industries",
            state=POState.SUBMITTED, approval_status=POApprovalStatus.AUTO_APPROVED,
            line_items=[POLineItem(item_sku="NS-1000ML", item_name="Normal Saline 1000mL", quantity=100, unit_price=3.50,
                                   extended_price=350.0, contract_tier=ContractTier.GPO_CONTRACT, criticality=ItemCriticality.CRITICAL)],
            total_cost=350.0, closet_id="CLO-ICU-01",
        ),
        PurchaseOrder(
            id="PO-002", scan_id="SCAN-001", vendor_id="VND-CARDINAL", vendor_name="Cardinal Health",
            state=POState.PENDING_APPROVAL, approval_status=POApprovalStatus.PENDING_HUMAN,
            line_items=[POLineItem(item_sku="GOWN-STERILE-L", item_name="Sterile Gown Large", quantity=60, unit_price=14.00,
                                   extended_price=840.0, contract_tier=ContractTier.SPOT_BUY, criticality=ItemCriticality.CRITICAL)],
            total_cost=1260.0, closet_id="CLO-SURG-01", requires_human_approval=True,
        ),
        PurchaseOrder(
            id="PO-003", scan_id="SCAN-001", vendor_id="VND-MCKESSON", vendor_name="McKesson Medical",
            state=POState.CREATED,
            line_items=[POLineItem(item_sku="GAUZE-4X4", item_name="Gauze Pads 4x4", quantity=200, unit_price=4.25,
                                   extended_price=850.0, contract_tier=ContractTier.PREFERRED, criticality=ItemCriticality.STANDARD)],
            total_cost=850.0, closet_id="CLO-SURG-01",
        ),
    ]


@pytest.fixture
def sample_shipments() -> list[Shipment]:
    """Shipments in various states."""
    return [
        Shipment(id="SHP-001", po_id="PO-001", vendor_id="VND-MEDLINE", closet_id="CLO-ICU-01",
                 state=ShipmentState.IN_TRANSIT, carrier="MedExpress", items_count=100),
        Shipment(id="SHP-002", po_id="PO-002", vendor_id="VND-CARDINAL",
                 closet_id="CLO-SURG-01", state=ShipmentState.CREATED, items_count=60),
    ]


# ---------------------------------------------------------------------------
# FastAPI async test client
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_client():
    """Async HTTP client wired to the FastAPI app (no real server needed).

    Resets the singleton stores before each test so endpoint tests get clean state.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.state import store as singleton_state_store
    from app.events import event_store as singleton_event_store
    from app.messages import message_store as singleton_message_store
    from app.metrics import metrics_store as singleton_metrics_store

    singleton_state_store.clear()
    singleton_event_store.clear()
    singleton_message_store.clear()
    singleton_metrics_store.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    singleton_state_store.clear()
    singleton_event_store.clear()
    singleton_message_store.clear()
    singleton_metrics_store.clear()
