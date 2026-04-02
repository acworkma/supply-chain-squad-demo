import { Bot, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { agentColor } from "@/lib/colors";
import type { AgentMessage } from "@/types/api";

/* ── Agent definitions ─────────────────────────────────────────── */

const AGENT_DIRECTORY = [
  { name: "supply-coordinator", role: "Supply Coordinator", desc: "The central hub. Orchestrates the entire closet replenishment workflow — from scan initiation through vendor sourcing, ordering, and restocking." },
  { name: "supply-scanner", role: "Supply Scanner Agent", desc: "Scans supply closets, counts inventory levels, and identifies items below par. Triggers reorder analysis." },
  { name: "catalog-sourcer", role: "Catalog Sourcer Agent", desc: "Looks up vendor catalogs for items needing reorder. Compares pricing, stock status, and contract tiers to find the best source." },
  { name: "order-manager", role: "Order Manager Agent", desc: "Creates purchase orders, manages approvals, submits to vendors, and tracks shipment through delivery and restocking." },
  { name: "compliance-gate", role: "Compliance Gate Agent", desc: "Enforces the $1,000 auto-approval threshold. Escalates critical shortages. Reviews POs for policy compliance." },
];

/* ── Props ──────────────────────────────────────────────────────── */

interface AgentDirectoryProps {
  isOpen: boolean;
  onToggle: () => void;
  messages: AgentMessage[];
}

/* ── Component ─────────────────────────────────────────────────── */

export function AgentDirectory({ isOpen, onToggle, messages }: AgentDirectoryProps) {
  const activeAgent = messages.length > 0 ? messages[messages.length - 1].agent_name : null;

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="h-full w-10 rounded-lg border border-tower-border bg-tower-surface flex flex-col items-center justify-center gap-3 transition-colors hover:border-tower-accent/40 hover:bg-tower-accent/5 group"
      >
        <Bot className="h-4 w-4 text-gray-500 group-hover:text-tower-accent transition-colors" />
        <span className="text-[10px] font-semibold tracking-widest text-gray-500 group-hover:text-gray-300 uppercase [writing-mode:vertical-lr] rotate-180 transition-colors">
          Agents
        </span>
        <ChevronLeft className="h-3 w-3 text-gray-500 group-hover:text-gray-300 transition-colors" />
      </button>
    );
  }

  return (
    <section className="flex-1 rounded-lg border border-tower-border bg-tower-surface overflow-hidden flex flex-col">
      {/* Header — matches PaneHeader styling */}
      <div className="relative flex items-center gap-2.5 px-4 py-3 border-b border-tower-border">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-tower-accent/40 to-transparent" />
        <Bot className="h-4 w-4 text-tower-accent shrink-0" />
        <h2 className="text-sm font-semibold tracking-wide text-gray-200 uppercase flex-1">
          Agent Directory
        </h2>
        <button
          onClick={onToggle}
          className="p-1 rounded hover:bg-tower-accent/10 transition-colors"
        >
          <ChevronRight className="h-4 w-4 text-gray-400 hover:text-gray-200" />
        </button>
      </div>

      {/* Card list */}
      <div className="overflow-y-auto flex-1 p-2 flex flex-col gap-2">
        {AGENT_DIRECTORY.map((agent) => {
          const colors = agentColor(agent.name);
          const isActive = activeAgent?.toLowerCase() === agent.name.toLowerCase();

          return (
            <div
              key={agent.name}
              className={cn(
                "rounded-lg border p-3 transition-all duration-300 flex gap-2",
                isActive
                  ? `${colors.bg} border-current shadow-lg`
                  : "border-tower-border/50 bg-tower-surface/50"
              )}
              style={isActive ? { borderColor: `color-mix(in srgb, currentColor 40%, transparent)` } : undefined}
            >
              {/* Left accent bar */}
              <div
                className={cn(
                  "w-1 rounded-full shrink-0 transition-opacity duration-300",
                  isActive ? "opacity-100" : "opacity-30"
                )}
                style={{ backgroundColor: getAccentHex(colors.text) }}
              />

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className={cn("text-xs font-semibold", colors.text)}>
                  {agent.role}
                </p>
                <p className="text-[11px] text-gray-400 leading-relaxed mt-1">
                  {agent.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ── Helpers ────────────────────────────────────────────────────── */

/** Extract a raw Tailwind color from a text-* class for inline styles */
function getAccentHex(textClass: string): string {
  const map: Record<string, string> = {
    "text-blue-400": "#60a5fa",
    "text-purple-400": "#c084fc",
    "text-emerald-400": "#34d399",
    "text-amber-400": "#fbbf24",
    "text-cyan-400": "#22d3ee",
    "text-red-400": "#f87171",
    "text-green-400": "#4ade80",
    "text-gray-400": "#9ca3af",
  };
  return map[textClass] ?? "#9ca3af";
}
