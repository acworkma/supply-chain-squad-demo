import type { BedState, PatientState, IntentTag, TransportPriority } from "@/types/api";

// ── Patient state colors ───────────────────────────────────────

const patientStateColors: Record<PatientState, string> = {
  AWAITING_BED: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  BED_ASSIGNED: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  TRANSPORT_READY: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
  IN_TRANSIT: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  ARRIVED: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  DISCHARGED: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

export function patientStateBadge(state: PatientState): string {
  return patientStateColors[state] ?? "bg-gray-500/20 text-gray-400";
}

// ── Bed state colors ───────────────────────────────────────────

const bedStateColors: Record<BedState, string> = {
  OCCUPIED: "bg-red-500/20 text-red-400 border-red-500/40",
  RESERVED: "bg-amber-500/20 text-amber-400 border-amber-500/40",
  DIRTY: "bg-orange-500/20 text-orange-400 border-orange-500/40",
  CLEANING: "bg-yellow-500/20 text-yellow-400 border-yellow-500/40",
  READY: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
  BLOCKED: "bg-gray-500/20 text-gray-400 border-gray-500/40",
};

const bedStateDot: Record<BedState, string> = {
  OCCUPIED: "bg-red-400",
  RESERVED: "bg-amber-400",
  DIRTY: "bg-orange-400",
  CLEANING: "bg-yellow-400",
  READY: "bg-emerald-400",
  BLOCKED: "bg-gray-400",
};

export function bedStateBadge(state: BedState): string {
  return bedStateColors[state] ?? "bg-gray-500/20 text-gray-400";
}

export function bedStateDotColor(state: BedState): string {
  return bedStateDot[state] ?? "bg-gray-400";
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

// ── Transport priority colors ──────────────────────────────────

const transportPriorityColors: Record<TransportPriority, string> = {
  STAT: "bg-red-500/20 text-red-400",
  URGENT: "bg-amber-500/20 text-amber-400",
  ROUTINE: "bg-gray-500/20 text-gray-400",
};

export function transportPriorityBadge(priority: TransportPriority): string {
  return transportPriorityColors[priority] ?? "bg-gray-500/20 text-gray-400";
}

// ── Agent colors (by name keyword) ─────────────────────────────

const agentColors: Record<string, { ring: string; text: string; bg: string }> = {
  "bed-coord":  { ring: "ring-blue-500/50",   text: "text-blue-400",    bg: "bg-blue-500/20" },
  flow:         { ring: "ring-blue-500/50",   text: "text-blue-400",    bg: "bg-blue-500/20" },
  predictive:   { ring: "ring-purple-500/50", text: "text-purple-400",  bg: "bg-purple-500/20" },
  bed:          { ring: "ring-emerald-500/50",text: "text-emerald-400", bg: "bg-emerald-500/20" },
  evs:          { ring: "ring-amber-500/50",  text: "text-amber-400",   bg: "bg-amber-500/20" },
  transport:    { ring: "ring-cyan-500/50",   text: "text-cyan-400",    bg: "bg-cyan-500/20" },
  policy:       { ring: "ring-red-500/50",    text: "text-red-400",     bg: "bg-red-500/20" },
  doctor:       { ring: "ring-green-500/50",  text: "text-green-400",   bg: "bg-green-500/20" },
  surgical:     { ring: "ring-green-500/50",  text: "text-green-400",   bg: "bg-green-500/20" },
  supervisor:   { ring: "ring-green-500/50",  text: "text-green-400",   bg: "bg-green-500/20" },
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
  if (lower.includes("bed") || lower.includes("reservation")) return "bg-blue-500/20 text-blue-400";
  if (lower.includes("patient")) return "bg-emerald-500/20 text-emerald-400";
  if (lower.includes("evs") || lower.includes("task")) return "bg-amber-500/20 text-amber-400";
  if (lower.includes("transport")) return "bg-cyan-500/20 text-cyan-400";
  if (lower.includes("sla") || lower.includes("risk")) return "bg-red-500/20 text-red-400";
  return "bg-gray-500/20 text-gray-400";
}
