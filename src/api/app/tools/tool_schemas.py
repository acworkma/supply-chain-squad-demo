"""JSON-schema-style tool definitions for Azure AI Foundry agents.

Each schema follows the OpenAI function-calling format consumed by the
Foundry agents SDK: ``{"type": "function", "function": {...}}``.

The v2 ``AGENT_TOOLS_V2`` mapping provides FunctionTool model objects
for ``PromptAgentDefinition.tools`` (``agents.create_version()``).
"""

from azure.ai.projects.models import FunctionTool

# ── Read-only tools ─────────────────────────────────────────────────

GET_SCAN = {
    "type": "function",
    "function": {
        "name": "get_scan",
        "description": "Look up a single closet scan result by ID. Returns scan state, closet, items scanned, items below par, and linked PO IDs.",
        "parameters": {
            "type": "object",
            "properties": {
                "scan_id": {"type": "string", "description": "The unique scan identifier (e.g. SCAN-001)."},
            },
            "required": ["scan_id"],
        },
    },
}

GET_ITEMS = {
    "type": "function",
    "function": {
        "name": "get_items",
        "description": "List supply items in hospital closets, optionally filtered by closet, category, and/or criticality. Returns item ID, SKU, name, quantities, par level, and days until stockout.",
        "parameters": {
            "type": "object",
            "properties": {
                "closet_id": {"type": "string", "description": "Filter by closet (e.g. 'CLO-ICU-01'). Omit to return all closets."},
                "category": {"type": "string", "enum": ["IV_THERAPY", "SURGICAL", "PPE", "WOUND_CARE", "CLEANING", "LINEN", "GENERAL", "SHARPS"], "description": "Filter by item category."},
                "criticality": {"type": "string", "enum": ["CRITICAL", "STANDARD", "LOW"], "description": "Filter by item criticality."},
            },
            "required": [],
        },
    },
}

GET_VENDORS = {
    "type": "function",
    "function": {
        "name": "get_vendors",
        "description": "List vendors, optionally filtered by contract tier. Returns vendor name, lead times, minimum order value, and contract tier.",
        "parameters": {
            "type": "object",
            "properties": {
                "contract_tier": {"type": "string", "enum": ["GPO_CONTRACT", "PREFERRED", "SPOT_BUY"], "description": "Filter by contract tier."},
            },
            "required": [],
        },
    },
}

GET_PURCHASE_ORDERS = {
    "type": "function",
    "function": {
        "name": "get_purchase_orders",
        "description": "List purchase orders, optionally filtered by state. Returns PO details including vendor, line items, total cost, and approval status.",
        "parameters": {
            "type": "object",
            "properties": {
                "po_state": {"type": "string", "enum": ["CREATED", "PENDING_APPROVAL", "APPROVED", "SUBMITTED", "CONFIRMED", "SHIPPED", "RECEIVED", "CANCELLED"], "description": "Filter by PO state."},
            },
            "required": [],
        },
    },
}

GET_SHIPMENTS = {
    "type": "function",
    "function": {
        "name": "get_shipments",
        "description": "List shipments, optionally filtered by state. Returns shipment details including carrier, tracking number, and expected delivery.",
        "parameters": {
            "type": "object",
            "properties": {
                "shipment_state": {"type": "string", "enum": ["CREATED", "SHIPPED", "IN_TRANSIT", "DELIVERED", "DELAYED"], "description": "Filter by shipment state."},
            },
            "required": [],
        },
    },
}

# ── Scan lifecycle ──────────────────────────────────────────────────

INITIATE_SCAN = {
    "type": "function",
    "function": {
        "name": "initiate_scan",
        "description": "Initiate a closet scan. Creates a ScanResult in INITIATED state and emits a ClosetScanInitiated event.",
        "parameters": {
            "type": "object",
            "properties": {
                "closet_id": {"type": "string", "description": "The closet to scan (e.g. CLO-ICU-01)."},
            },
            "required": ["closet_id"],
        },
    },
}

ANALYZE_SCAN = {
    "type": "function",
    "function": {
        "name": "analyze_scan",
        "description": "Analyze a scan: compare current quantities against par levels, identify items below par, compute days-until-stockout, and transition scan to ITEMS_IDENTIFIED.",
        "parameters": {
            "type": "object",
            "properties": {
                "scan_id": {"type": "string", "description": "The scan to analyze."},
            },
            "required": ["scan_id"],
        },
    },
}

# ── Sourcing ────────────────────────────────────────────────────────

LOOKUP_VENDOR_CATALOG = {
    "type": "function",
    "function": {
        "name": "lookup_vendor_catalog",
        "description": "Look up the vendor catalog for a given item SKU. Returns catalog entries across all vendors with pricing, stock status, and lead times. Recommends the best vendor by contract tier and availability.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_sku": {"type": "string", "description": "The item SKU to look up in vendor catalogs."},
            },
            "required": ["item_sku"],
        },
    },
}

# ── Purchase order lifecycle ────────────────────────────────────────

CREATE_PURCHASE_ORDER = {
    "type": "function",
    "function": {
        "name": "create_purchase_order",
        "description": "Create a purchase order for a scan's reorder list. Builds line items from the reorder items, computes total cost. POs under $1000 are auto-approved; POs >= $1000 require human approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "scan_id": {"type": "string", "description": "The scan that identified items to reorder."},
                "vendor_id": {"type": "string", "description": "The vendor to order from."},
            },
            "required": ["scan_id", "vendor_id"],
        },
    },
}

APPROVE_PURCHASE_ORDER = {
    "type": "function",
    "function": {
        "name": "approve_purchase_order",
        "description": "Approve or reject a purchase order that is pending human approval. Transitions PO state from PENDING_APPROVAL to APPROVED (or CANCELLED if rejected).",
        "parameters": {
            "type": "object",
            "properties": {
                "po_id": {"type": "string", "description": "The purchase order to approve or reject."},
                "approved": {"type": "boolean", "description": "True to approve, false to reject."},
                "note": {"type": "string", "description": "Optional approval/rejection note."},
            },
            "required": ["po_id", "approved"],
        },
    },
}

SUBMIT_PURCHASE_ORDER = {
    "type": "function",
    "function": {
        "name": "submit_purchase_order",
        "description": "Submit an approved purchase order to the vendor. Transitions PO from APPROVED to SUBMITTED.",
        "parameters": {
            "type": "object",
            "properties": {
                "po_id": {"type": "string", "description": "The purchase order to submit."},
            },
            "required": ["po_id"],
        },
    },
}

# ── Fulfillment ─────────────────────────────────────────────────────

CREATE_SHIPMENT = {
    "type": "function",
    "function": {
        "name": "create_shipment",
        "description": "Create a shipment record for a confirmed purchase order. Generates a tracking number and sets expected delivery based on vendor lead time.",
        "parameters": {
            "type": "object",
            "properties": {
                "po_id": {"type": "string", "description": "The purchase order being shipped."},
                "carrier": {"type": "string", "description": "Carrier name (e.g. 'MedLine Logistics')."},
            },
            "required": ["po_id", "carrier"],
        },
    },
}

RECEIVE_SHIPMENT = {
    "type": "function",
    "function": {
        "name": "receive_shipment",
        "description": "Mark a shipment as delivered and update closet supply item quantities. Transitions shipment to DELIVERED, PO to RECEIVED, and increments item current_quantity values.",
        "parameters": {
            "type": "object",
            "properties": {
                "shipment_id": {"type": "string", "description": "The shipment being received."},
            },
            "required": ["shipment_id"],
        },
    },
}

# ── Generic event & escalation ──────────────────────────────────────

PUBLISH_EVENT = {
    "type": "function",
    "function": {
        "name": "publish_event",
        "description": "Emit a generic event to the event stream. Use for events not covered by specific tools.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "description": "The event type string."},
                "entity_id": {"type": "string", "description": "The entity this event pertains to."},
                "payload": {"type": "object", "description": "Arbitrary event payload data."},
            },
            "required": ["event_type", "entity_id"],
        },
    },
}

ESCALATE = {
    "type": "function",
    "function": {
        "name": "escalate",
        "description": "Escalate an issue by emitting a CriticalShortageDetected event. Use when supply levels are critically low, compliance concerns arise, or vendor issues threaten patient care.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_type": {"type": "string", "description": "Category of issue (e.g. 'critical_shortage', 'compliance_violation', 'vendor_stockout')."},
                "entity_id": {"type": "string", "description": "The entity involved in the escalation."},
                "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"], "description": "Severity level."},
                "message": {"type": "string", "description": "Human-readable description of the issue."},
            },
            "required": ["issue_type", "entity_id", "severity", "message"],
        },
    },
}


# ── Per-agent tool sets (5 agents per DOMAIN-C-002) ─────────────────

SUPPLY_COORDINATOR_TOOLS = [GET_SCAN, GET_ITEMS, GET_VENDORS, GET_PURCHASE_ORDERS, GET_SHIPMENTS, PUBLISH_EVENT, ESCALATE]
SUPPLY_SCANNER_TOOLS = [GET_ITEMS, INITIATE_SCAN, ANALYZE_SCAN, PUBLISH_EVENT]
CATALOG_SOURCER_TOOLS = [GET_ITEMS, GET_VENDORS, LOOKUP_VENDOR_CATALOG, PUBLISH_EVENT]
ORDER_MANAGER_TOOLS = [GET_SCAN, GET_PURCHASE_ORDERS, CREATE_PURCHASE_ORDER, APPROVE_PURCHASE_ORDER, SUBMIT_PURCHASE_ORDER, CREATE_SHIPMENT, RECEIVE_SHIPMENT, PUBLISH_EVENT]
COMPLIANCE_GATE_TOOLS = [GET_PURCHASE_ORDERS, GET_ITEMS, APPROVE_PURCHASE_ORDER, ESCALATE, PUBLISH_EVENT]

AGENT_TOOLS: dict[str, list[dict]] = {
    "supply-coordinator": SUPPLY_COORDINATOR_TOOLS,
    "supply-scanner": SUPPLY_SCANNER_TOOLS,
    "catalog-sourcer": CATALOG_SOURCER_TOOLS,
    "order-manager": ORDER_MANAGER_TOOLS,
    "compliance-gate": COMPLIANCE_GATE_TOOLS,
}


# ── v2 FunctionTool objects (for PromptAgentDefinition.tools) ───────

def _to_function_tool(schema: dict) -> FunctionTool:
    """Convert a legacy dict schema to a FunctionTool model object."""
    fn = schema["function"]
    return FunctionTool(
        name=fn["name"],
        description=fn["description"],
        parameters=fn.get("parameters", {}),
    )


AGENT_TOOLS_V2: dict[str, list[FunctionTool]] = {
    agent_name: [_to_function_tool(s) for s in tools]
    for agent_name, tools in AGENT_TOOLS.items()
}
