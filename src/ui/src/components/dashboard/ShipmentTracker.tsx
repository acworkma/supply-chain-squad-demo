import { Truck, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { shipmentStateBadge } from "@/lib/colors";
import type { Shipment, ShipmentState } from "@/types/api";

interface ShipmentTrackerProps {
  shipments: Shipment[];
  loading: boolean;
  error: string | null;
}

const stateLabel: Record<ShipmentState, string> = {
  CREATED: "Pending",
  SHIPPED: "Shipped",
  IN_TRANSIT: "In Transit",
  DELIVERED: "Delivered",
  DELAYED: "Delayed ⚠️",
};

function formatDate(ts: string | undefined): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString([], { month: "short", day: "numeric" });
}

export function ShipmentTracker({ shipments, loading, error }: ShipmentTrackerProps) {
  if (error) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 text-tower-error text-xs">
        <AlertTriangle className="h-3.5 w-3.5" />
        <span>Failed to load: {error}</span>
      </div>
    );
  }

  if (loading && shipments.length === 0) {
    return (
      <div className="flex items-center justify-center gap-3 py-3 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-2 shrink-0">
          <Truck className="h-4 w-4 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">Loading shipments…</p>
      </div>
    );
  }

  if (shipments.length === 0) {
    return (
      <div className="flex items-center justify-center gap-3 py-3 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-2 shrink-0">
          <Truck className="h-4 w-4 text-tower-accent/60" />
        </div>
        <div>
          <p className="text-sm text-gray-400">No active shipments</p>
          <p className="text-xs text-gray-600">Shipments will appear here once POs are submitted</p>
        </div>
      </div>
    );
  }

  return (
    <div className="divide-y divide-tower-border/50">
      {shipments.map((s) => (
        <div
          key={s.id}
          className="flex items-start gap-3 px-3 py-2 hover:bg-white/2 transition-colors text-xs"
        >
          {/* Carrier badge */}
          <span className="inline-flex items-center rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase shrink-0 bg-tower-accent/10 text-tower-accent">
            {s.carrier}
          </span>

          {/* Main content */}
          <div className="flex flex-col gap-0.5 min-w-0 flex-1">
            <span className="text-gray-200 font-medium truncate">
              PO {s.po_id} → {s.closet_id}
            </span>
            {s.tracking_number && (
              <span className="text-gray-500 font-mono text-[10px] truncate">
                {s.tracking_number}
              </span>
            )}
            <span className="text-gray-500 text-[10px]">
              {s.items_count} {s.items_count === 1 ? "item" : "items"}
            </span>
          </div>

          {/* Right side: state + date */}
          <div className="flex flex-col items-end gap-1 shrink-0">
            <span
              className={cn(
                "inline-flex items-center rounded-sm px-1.5 py-0.5 text-[10px] font-semibold border transition-colors",
                shipmentStateBadge(s.state)
              )}
            >
              {stateLabel[s.state] ?? s.state}
            </span>
            <span className="text-gray-500 font-mono text-[10px]">
              {formatDate(s.expected_delivery)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
