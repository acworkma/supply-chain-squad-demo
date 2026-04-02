// ── State enums as string unions ────────────────────────────────

export type ItemCategory =
  | "IV_THERAPY"
  | "SURGICAL"
  | "PPE"
  | "WOUND_CARE"
  | "CLEANING"
  | "LINEN"
  | "GENERAL"
  | "SHARPS";

export type ItemCriticality = "CRITICAL" | "STANDARD" | "LOW";

export type ContractTier = "GPO_CONTRACT" | "PREFERRED" | "SPOT_BUY";

export type POState =
  | "CREATED"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "SUBMITTED"
  | "CONFIRMED"
  | "SHIPPED"
  | "RECEIVED"
  | "CANCELLED";

export type POApprovalStatus =
  | "AUTO_APPROVED"
  | "PENDING_HUMAN"
  | "HUMAN_APPROVED"
  | "HUMAN_REJECTED";

export type ScanState =
  | "INITIATED"
  | "ANALYZING"
  | "ITEMS_IDENTIFIED"
  | "SOURCING"
  | "ORDERING"
  | "PENDING_APPROVAL"
  | "COMPLETE";

export type VendorStockStatus =
  | "IN_STOCK"
  | "LOW_STOCK"
  | "OUT_OF_STOCK"
  | "DISCONTINUED";

export type ShipmentState =
  | "CREATED"
  | "SHIPPED"
  | "IN_TRANSIT"
  | "DELIVERED"
  | "DELAYED";

export type TaskState =
  | "CREATED"
  | "ACCEPTED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "ESCALATED"
  | "CANCELLED";

export type IntentTag = "PROPOSE" | "VALIDATE" | "EXECUTE" | "ESCALATE";

// ── Entity interfaces ──────────────────────────────────────────

export interface SupplyCloset {
  id: string;
  name: string;
  floor: string;
  unit: string;
  location: string;
}

export interface SupplyItem {
  id: string;
  sku: string;
  name: string;
  closet_id: string;
  category: ItemCategory;
  criticality: ItemCriticality;
  par_level: number;
  reorder_quantity: number;
  current_quantity: number;
  unit_of_measure: string;
  consumption_rate_per_day: number;
  last_restocked: string;
}

export interface Vendor {
  id: string;
  name: string;
  contract_tier: ContractTier;
  lead_time_days: number;
  expedite_lead_time_days: number;
  minimum_order_value: number;
}

export interface CatalogEntry {
  id: string;
  vendor_id: string;
  item_sku: string;
  unit_price: number;
  contract_tier: ContractTier;
  stock_status: VendorStockStatus;
  lead_time_days: number;
  substitute_sku?: string;
}

export interface POLineItem {
  item_sku: string;
  item_name: string;
  quantity: number;
  unit_price: number;
  extended_price: number;
  contract_tier: ContractTier;
  criticality: ItemCriticality;
}

export interface PurchaseOrder {
  id: string;
  scan_id: string;
  vendor_id: string;
  vendor_name: string;
  state: POState;
  approval_status: POApprovalStatus;
  line_items: POLineItem[];
  total_cost: number;
  created_at: string;
  approved_at?: string;
  submitted_at?: string;
  requires_human_approval: boolean;
  approval_note: string;
  closet_id: string;
}

export interface ReorderItem {
  item_id: string;
  item_sku: string;
  item_name: string;
  current_quantity: number;
  par_level: number;
  reorder_quantity: number;
  criticality: ItemCriticality;
  days_until_stockout: number;
  recommended_vendor_id?: string;
  recommended_unit_price?: number;
}

export interface ScanResult {
  id: string;
  closet_id: string;
  state: ScanState;
  initiated_at: string;
  completed_at?: string;
  items_scanned: number;
  items_below_par: number;
  items_to_reorder: ReorderItem[];
  purchase_order_ids: string[];
}

export interface Shipment {
  id: string;
  po_id: string;
  vendor_id: string;
  closet_id: string;
  state: ShipmentState;
  carrier: string;
  tracking_number?: string;
  expected_delivery?: string;
  delivered_at?: string;
  items_count: number;
}

export interface StateDiff {
  from_state: string;
  to_state: string;
}

export interface Event {
  id: string;
  sequence: number;
  timestamp: string;
  event_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
  state_diff: StateDiff | null;
}

export interface AgentMessage {
  id: string;
  timestamp: string;
  agent_name: string;
  agent_role: string;
  content: string;
  intent_tag: IntentTag;
  related_event_ids: string[];
}

// ── API response shapes ────────────────────────────────────────

export interface StateResponse {
  closets: Record<string, SupplyCloset>;
  supply_items: Record<string, SupplyItem>;
  vendors: Record<string, Vendor>;
  catalog: Record<string, CatalogEntry>;
  purchase_orders: Record<string, PurchaseOrder>;
  scans: Record<string, ScanResult>;
  shipments: Record<string, Shipment>;
}
