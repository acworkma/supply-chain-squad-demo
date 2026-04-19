import { Package, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { itemStatusColor, itemStatusDot, criticalityBadge } from "@/lib/colors";
import type { SupplyItem } from "@/types/api";

interface InventoryBoardProps {
  supplyItems: SupplyItem[];
  loading: boolean;
  error: string | null;
}

export function InventoryBoard({ supplyItems, loading, error }: InventoryBoardProps) {
  if (error) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 text-tower-error text-xs">
        <AlertTriangle className="h-3.5 w-3.5" />
        <span>Failed to load: {error}</span>
      </div>
    );
  }

  if (loading && supplyItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-3 mb-3">
          <Package className="h-5 w-5 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">Loading supply items…</p>
      </div>
    );
  }

  if (supplyItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-3 mb-3">
          <Package className="h-5 w-5 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">No supply items loaded</p>
        <p className="text-xs text-gray-600 mt-1">Closet inventory will appear here during scenarios</p>
      </div>
    );
  }

  // Group items by closet
  const closetMap = new Map<string, SupplyItem[]>();
  for (const item of supplyItems) {
    const group = closetMap.get(item.closet_id) ?? [];
    group.push(item);
    closetMap.set(item.closet_id, group);
  }

  const sortedClosets = [...closetMap.entries()].sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="p-3 space-y-3">
      {sortedClosets.map(([closetId, items]) => {
        const sorted = items.sort((a, b) => a.sku.localeCompare(b.sku));
        return (
          <div key={closetId}>
            <h3 className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1.5 px-1">
              {closetId}
            </h3>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-1.5">
              {sorted.map((item) => (
                <div
                  key={item.id}
                  className={cn(
                    "rounded-sm border px-2 py-1.5 text-[11px] transition-colors",
                    itemStatusColor(item.current_quantity, item.par_level, item.criticality)
                  )}
                >
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", itemStatusDot(item.current_quantity, item.par_level, item.criticality))} />
                    <span className="font-semibold font-mono truncate" title={item.sku}>
                      {item.sku}
                    </span>
                    <span className={cn("ml-auto text-[9px] px-1 rounded-sm", criticalityBadge(item.criticality))}>
                      {item.criticality}
                    </span>
                  </div>
                  <p className="text-[10px] opacity-80 truncate" title={item.name}>
                    {item.name}
                  </p>
                  <div className="flex items-center justify-between mt-0.5 text-[9px] opacity-70 font-mono">
                    <span title="Current / Par">{item.current_quantity} / {item.par_level} {item.unit_of_measure}</span>
                    <span title={`Category: ${item.category}`}>{item.category.replace(/_/g, " ")}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
