import { ShoppingCart, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { poStateBadge, poApprovalBadge } from "@/lib/colors";
import type { PurchaseOrder } from "@/types/api";

interface OrderQueueProps {
  purchaseOrders: PurchaseOrder[];
  loading: boolean;
  error: string | null;
}

export function OrderQueue({ purchaseOrders, loading, error }: OrderQueueProps) {
  if (error) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 text-tower-error text-xs">
        <AlertTriangle className="h-3.5 w-3.5" />
        <span>Failed to load: {error}</span>
      </div>
    );
  }

  if (loading && purchaseOrders.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-3 mb-3">
          <ShoppingCart className="h-5 w-5 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">Loading purchase orders…</p>
      </div>
    );
  }

  if (purchaseOrders.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-3 mb-3">
          <ShoppingCart className="h-5 w-5 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">No purchase orders</p>
        <p className="text-xs text-gray-600 mt-1">Start a scenario to see purchase orders</p>
      </div>
    );
  }

  const sorted = [...purchaseOrders].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-gray-500 uppercase tracking-wider border-b border-tower-border">
          <th className="text-left px-3 py-2 font-medium">PO #</th>
          <th className="text-left px-3 py-2 font-medium">Vendor</th>
          <th className="text-left px-3 py-2 font-medium">State</th>
          <th className="text-left px-3 py-2 font-medium">Approval</th>
          <th className="text-center px-3 py-2 font-medium">Items</th>
          <th className="text-right px-3 py-2 font-medium">Total</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((po) => (
          <tr
            key={po.id}
            className="border-b border-tower-border/50 hover:bg-white/2 transition-colors"
          >
            <td className="px-3 py-1.5 text-gray-400 font-mono">{po.id}</td>
            <td className="px-3 py-1.5 text-gray-200 font-medium truncate max-w-[120px]">
              {po.vendor_name}
            </td>
            <td className="px-3 py-1.5">
              <span
                className={cn(
                  "inline-flex items-center rounded-sm px-1.5 py-0.5 text-[10px] font-semibold border transition-colors",
                  poStateBadge(po.state)
                )}
              >
                {po.state.replace(/_/g, " ")}
              </span>
            </td>
            <td className="px-3 py-1.5">
              <span
                className={cn(
                  "inline-flex items-center rounded-sm px-1.5 py-0.5 text-[10px] font-semibold border transition-colors",
                  poApprovalBadge(po.approval_status)
                )}
              >
                {po.approval_status.replace(/_/g, " ")}
              </span>
            </td>
            <td className="px-3 py-1.5 text-center text-gray-400 font-mono">
              {po.line_items.length}
            </td>
            <td className="px-3 py-1.5 text-right text-gray-400 font-mono">
              ${po.total_cost.toFixed(2)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
