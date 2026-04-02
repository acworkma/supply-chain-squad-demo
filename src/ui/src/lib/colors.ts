import type {
  POState,
  POApprovalStatus,
  ScanState,
  ShipmentState,
  ContractTier,
  ItemCriticality,
  VendorStockStatus,
  IntentTag,
} from "@/types/api";

// ── Item stock status colors (for ClosetBoard) ────────────────

/**
 * Returns a badge class string for a supply item based on its current
 * quantity relative to par level and criticality.
 *
 * Four tiers:
 *   🔴 RED    — critically low: CRITICAL items < 50% par, or any item < 30% par
 *   🟠 AMBER  — low: below par level but not critical
 *   🟢 GREEN  — stocked: at or above par level
 *   ⚫ GRAY   — empty: zero quantity
 */
export function itemStatusColor(
  currentQuantity: number,
  parLevel: number,
  criticality: ItemCriticality,
): string {
  if (currentQuantity === 0) return "bg-gray-500/20 text-gray-400 border-gray-500/40";
  const ratio = parLevel > 0 ? currentQuantity / parLevel : 1;
  if (ratio < 0.3 || (ratio < 0.5 && criticality === "CRITICAL"))
    return "bg-red-500/20 text-red-400 border-red-500/40";
  if (currentQuantity < parLevel)
    return "bg-amber-500/20 text-amber-400 border-amber-500/40";
  return "bg-emerald-500/20 text-emerald-400 border-emerald-500/40";
}

export function itemStatusDot(
  currentQuantity: number,
  parLevel: number,
  criticality: ItemCriticality,
): string {
  if (currentQuantity === 0) return "bg-gray-500";
  const ratio = parLevel > 0 ? currentQuantity / parLevel : 1;
  if (ratio < 0.3 || (ratio < 0.5 && criticality === "CRITICAL")) return "bg-red-500";
  if (currentQuantity < parLevel) return "bg-amber-500";
  return "bg-emerald-500";
}

// ── PO state colors ────────────────────────────────────────────

const poStateColors: Record<POState, string> = {
  CREATED: "bg-gray-400/20 text-gray-400 border-gray-400/30",
  PENDING_APPROVAL: "bg-amber-400/20 text-amber-400 border-amber-400/30",
  APPROVED: "bg-blue-400/20 text-blue-400 border-blue-400/30",
  SUBMITTED: "bg-cyan-400/20 text-cyan-400 border-cyan-400/30",
  CONFIRMED: "bg-indigo-400/20 text-indigo-400 border-indigo-400/30",
  SHIPPED: "bg-violet-400/20 text-violet-400 border-violet-400/30",
  RECEIVED: "bg-emerald-400/20 text-emerald-400 border-emerald-400/30",
  CANCELLED: "bg-red-400/20 text-red-400 border-red-400/30",
};

export function poStateBadge(state: POState): string {
  return poStateColors[state] ?? "bg-gray-500/20 text-gray-400";
}

// ── PO approval status colors ──────────────────────────────────

const poApprovalColors: Record<POApprovalStatus, string> = {
  AUTO_APPROVED: "bg-emerald-400/20 text-emerald-400 border-emerald-400/30",
  PENDING_HUMAN: "bg-amber-400/20 text-amber-400 border-amber-400/30",
  HUMAN_APPROVED: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  HUMAN_REJECTED: "bg-red-400/20 text-red-400 border-red-400/30",
};

export function poApprovalBadge(status: POApprovalStatus): string {
  return poApprovalColors[status] ?? "bg-gray-500/20 text-gray-400";
}

// ── Scan state colors ──────────────────────────────────────────

const scanStateColors: Record<ScanState, string> = {
  INITIATED: "bg-gray-400/20 text-gray-400 border-gray-400/30",
  ANALYZING: "bg-blue-400/20 text-blue-400 border-blue-400/30",
  ITEMS_IDENTIFIED: "bg-cyan-400/20 text-cyan-400 border-cyan-400/30",
  SOURCING: "bg-amber-400/20 text-amber-400 border-amber-400/30",
  ORDERING: "bg-indigo-400/20 text-indigo-400 border-indigo-400/30",
  PENDING_APPROVAL: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  COMPLETE: "bg-emerald-400/20 text-emerald-400 border-emerald-400/30",
};

export function scanStateBadge(state: ScanState): string {
  return scanStateColors[state] ?? "bg-gray-500/20 text-gray-400";
}

// ── Contract tier colors ───────────────────────────────────────

const contractTierColors: Record<ContractTier, string> = {
  GPO_CONTRACT: "bg-emerald-400/20 text-emerald-400 border-emerald-400/30",
  PREFERRED: "bg-blue-400/20 text-blue-400 border-blue-400/30",
  SPOT_BUY: "bg-amber-400/20 text-amber-400 border-amber-400/30",
};

export function contractTierBadge(tier: ContractTier): string {
  return contractTierColors[tier] ?? "bg-gray-500/20 text-gray-400";
}

// ── Item criticality colors ────────────────────────────────────

const criticalityColors: Record<ItemCriticality, string> = {
  CRITICAL: "bg-red-400/20 text-red-400 border-red-400/30",
  STANDARD: "bg-blue-400/20 text-blue-400 border-blue-400/30",
  LOW: "bg-gray-400/20 text-gray-400 border-gray-400/30",
};

export function criticalityBadge(criticality: ItemCriticality): string {
  return criticalityColors[criticality] ?? "bg-gray-500/20 text-gray-400";
}

// ── Vendor stock status colors ─────────────────────────────────

const vendorStockColors: Record<VendorStockStatus, string> = {
  IN_STOCK: "bg-emerald-400/20 text-emerald-400 border-emerald-400/30",
  LOW_STOCK: "bg-amber-400/20 text-amber-400 border-amber-400/30",
  OUT_OF_STOCK: "bg-red-400/20 text-red-400 border-red-400/30",
  DISCONTINUED: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

export function vendorStockBadge(status: VendorStockStatus): string {
  return vendorStockColors[status] ?? "bg-gray-500/20 text-gray-400";
}

// ── Shipment state colors ──────────────────────────────────────

const shipmentStateColors: Record<ShipmentState, string> = {
  CREATED: "bg-gray-400/20 text-gray-400 border-gray-400/30",
  SHIPPED: "bg-blue-400/20 text-blue-400 border-blue-400/30",
  IN_TRANSIT: "bg-violet-400/20 text-violet-400 border-violet-400/30",
  DELIVERED: "bg-emerald-400/20 text-emerald-400 border-emerald-400/30",
  DELAYED: "bg-amber-500/20 text-amber-400 border-amber-500/30",
};

export function shipmentStateBadge(state: ShipmentState): string {
  return shipmentStateColors[state] ?? "bg-gray-500/20 text-gray-400";
}

// ── Intent tag colors ──────────────────────────────────────────

const intentTagColors: Record<IntentTag, string> = {
  PROPOSE: "bg-blue-500/20 text-blue-400",
  VALIDATE: "bg-emerald-500/20 text-emerald-400",
  EXECUTE: "bg-cyan-500/20 text-cyan-400",
  ESCALATE: "bg-red-500/20 text-red-400",
};

export function intentTagBadge(tag: IntentTag): string {
  return intentTagColors[tag] ?? "bg-gray-500/20 text-gray-400";
}

// ── Agent colors (by name keyword) ─────────────────────────────

const agentColors: Record<string, { ring: string; text: string; bg: string }> = {
  "supply-coord":    { ring: "ring-blue-500/50",    text: "text-blue-400",    bg: "bg-blue-500/20" },
  coordinator:       { ring: "ring-blue-500/50",    text: "text-blue-400",    bg: "bg-blue-500/20" },
  scanner:           { ring: "ring-purple-500/50",  text: "text-purple-400",  bg: "bg-purple-500/20" },
  "supply-scanner":  { ring: "ring-purple-500/50",  text: "text-purple-400",  bg: "bg-purple-500/20" },
  "catalog-sourcer": { ring: "ring-emerald-500/50", text: "text-emerald-400", bg: "bg-emerald-500/20" },
  sourcer:           { ring: "ring-emerald-500/50", text: "text-emerald-400", bg: "bg-emerald-500/20" },
  "order-manager":   { ring: "ring-amber-500/50",   text: "text-amber-400",   bg: "bg-amber-500/20" },
  order:             { ring: "ring-amber-500/50",   text: "text-amber-400",   bg: "bg-amber-500/20" },
  "compliance-gate": { ring: "ring-red-500/50",     text: "text-red-400",     bg: "bg-red-500/20" },
  compliance:        { ring: "ring-red-500/50",     text: "text-red-400",     bg: "bg-red-500/20" },
};

const defaultAgentColor = { ring: "ring-gray-500/50", text: "text-gray-400", bg: "bg-gray-500/20" };

export function agentColor(agentName: string) {
  const lower = agentName.toLowerCase();
  for (const [key, colors] of Object.entries(agentColors)) {
    if (lower.includes(key)) return colors;
  }
  return defaultAgentColor;
}

// ── Event type colors (by prefix keyword) ──────────────────────

export function eventTypeColor(eventType: string): string {
  const lower = eventType.toLowerCase();
  // Scan lifecycle
  if (lower.includes("scan") || lower.includes("below_par") || lower.includes("belowpar") || lower.includes("items_identified"))
    return "bg-purple-500/20 text-purple-400";
  // Sourcing
  if (lower.includes("vendor") || lower.includes("substitute") || lower.includes("catalog") || lower.includes("sourcing"))
    return "bg-emerald-500/20 text-emerald-400";
  // Purchase orders
  if (lower.includes("po_") || lower.includes("pocreated") || lower.includes("purchase") || lower.includes("approval") || lower.includes("approved") || lower.includes("rejected") || lower.includes("submitted") || lower.includes("confirmed"))
    return "bg-amber-500/20 text-amber-400";
  // Shipment / delivery
  if (lower.includes("shipment") || lower.includes("deliver"))
    return "bg-cyan-500/20 text-cyan-400";
  // Restocking
  if (lower.includes("restock"))
    return "bg-blue-500/20 text-blue-400";
  // Critical / escalation
  if (lower.includes("critical") || lower.includes("shortage") || lower.includes("escalat"))
    return "bg-red-500/20 text-red-400";
  return "bg-gray-500/20 text-gray-400";
}
