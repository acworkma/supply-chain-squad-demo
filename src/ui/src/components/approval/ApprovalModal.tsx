import { useState, useCallback } from "react";
import { AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PurchaseOrder } from "@/types/api";

interface ApprovalModalProps {
  po: PurchaseOrder;
  onClose: () => void;
}

export function ApprovalModal({ po, onClose }: ApprovalModalProps) {
  const [submitting, setSubmitting] = useState(false);
  const [note, setNote] = useState("");

  const handleDecision = useCallback(
    async (approved: boolean) => {
      setSubmitting(true);
      try {
        const res = await fetch(`/api/approval/${po.id}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approved, note: note || undefined }),
        });
        if (res.ok) {
          onClose();
        }
      } finally {
        setSubmitting(false);
      }
    },
    [po.id, note, onClose],
  );

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-lg rounded-lg border border-tower-border bg-tower-surface shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-tower-border px-6 py-4">
          <AlertTriangle className="h-6 w-6 text-amber-400 shrink-0" />
          <div>
            <h2 className="text-lg font-semibold text-gray-100">
              PO Approval Required
            </h2>
            <p className="text-xs text-gray-400">
              Human-in-the-loop — this PO exceeds the $1,000 auto-approval
              threshold
            </p>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-4 px-6 py-5">
          {/* PO Summary */}
          <div className="rounded border border-tower-border bg-tower-bg p-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">PO ID</span>
              <span className="font-mono text-gray-200">{po.id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Vendor</span>
              <span className="text-gray-200">{po.vendor_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Total Cost</span>
              <span className="text-amber-400 font-semibold">
                ${po.total_cost.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Line Items</span>
              <span className="text-gray-200">{po.line_items.length}</span>
            </div>
          </div>

          {/* Line items detail */}
          <div className="max-h-40 overflow-y-auto rounded border border-tower-border bg-tower-bg">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-tower-border text-gray-500">
                  <th className="px-3 py-2 text-left">Item</th>
                  <th className="px-3 py-2 text-right">Qty</th>
                  <th className="px-3 py-2 text-right">Unit $</th>
                  <th className="px-3 py-2 text-right">Ext $</th>
                </tr>
              </thead>
              <tbody>
                {po.line_items.map((li, i) => (
                  <tr key={i} className="border-b border-tower-border/50 text-gray-300">
                    <td className="px-3 py-1.5">{li.item_name}</td>
                    <td className="px-3 py-1.5 text-right">{li.quantity}</td>
                    <td className="px-3 py-1.5 text-right">${li.unit_price.toFixed(2)}</td>
                    <td className="px-3 py-1.5 text-right">${li.extended_price.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Note */}
          <textarea
            className="w-full rounded border border-tower-border bg-tower-bg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:border-tower-accent/50 focus:outline-none"
            rows={2}
            placeholder="Approval note (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 border-t border-tower-border px-6 py-4">
          <button
            onClick={() => handleDecision(false)}
            disabled={submitting}
            className={cn(
              "inline-flex items-center gap-1.5 rounded px-4 py-2 text-sm font-medium transition-colors",
              "border border-red-500/40 text-red-400 hover:bg-red-500/10",
              "disabled:opacity-40 disabled:cursor-not-allowed",
            )}
          >
            <XCircle className="h-4 w-4" />
            Reject
          </button>
          <button
            onClick={() => handleDecision(true)}
            disabled={submitting}
            className={cn(
              "inline-flex items-center gap-1.5 rounded px-4 py-2 text-sm font-medium transition-colors",
              "border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10",
              "disabled:opacity-40 disabled:cursor-not-allowed",
            )}
          >
            <CheckCircle className="h-4 w-4" />
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
