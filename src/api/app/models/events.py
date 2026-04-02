"""Event type definitions and the base Event model for the supply-closet replenishment domain."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Scan lifecycle ──────────────────────────────────────────────────
CLOSET_SCAN_INITIATED = "ClosetScanInitiated"
CLOSET_SCAN_ANALYZED = "ClosetScanAnalyzed"
ITEMS_BELOW_PAR_IDENTIFIED = "ItemsBelowParIdentified"

# ── Sourcing ────────────────────────────────────────────────────────
VENDOR_LOOKUP_COMPLETED = "VendorLookupCompleted"
VENDOR_ITEM_OUT_OF_STOCK = "VendorItemOutOfStock"
SUBSTITUTE_RECOMMENDED = "SubstituteRecommended"

# ── Purchase orders ─────────────────────────────────────────────────
PO_CREATED = "POCreated"
PO_AUTO_APPROVED = "POAutoApproved"
PO_PENDING_HUMAN_APPROVAL = "POPendingHumanApproval"
PO_HUMAN_APPROVED = "POHumanApproved"
PO_HUMAN_REJECTED = "POHumanRejected"
PO_SUBMITTED = "POSubmitted"
PO_CONFIRMED = "POConfirmed"

# ── Fulfillment ─────────────────────────────────────────────────────
SHIPMENT_CREATED = "ShipmentCreated"
SHIPMENT_DELIVERED = "ShipmentDelivered"
CLOSET_RESTOCKED = "ClosetRestocked"

# ── Escalation / urgency ───────────────────────────────────────────
CRITICAL_SHORTAGE_DETECTED = "CriticalShortageDetected"


class StateDiff(BaseModel):
    from_state: str
    to_state: str


class Event(BaseModel):
    """Immutable event appended to the event store."""

    id: str
    sequence: int = 0
    timestamp: datetime = Field(default_factory=_utcnow)
    event_type: str
    entity_id: str
    payload: dict = Field(default_factory=dict)
    state_diff: Optional[StateDiff] = None
