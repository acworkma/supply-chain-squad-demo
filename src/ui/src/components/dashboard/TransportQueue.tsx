import { Truck, AlertTriangle, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { transportPriorityBadge } from "@/lib/colors";
import type { Transport, Patient } from "@/types/api";

interface TransportQueueProps {
  transports: Transport[];
  patients: Record<string, Patient>;
  loading: boolean;
  error: string | null;
}

const stateLabel: Record<string, string> = {
  CREATED: "Pending",
  ACCEPTED: "Accepted",
  IN_PROGRESS: "In Transit",
  COMPLETED: "Done",
  ESCALATED: "Escalated",
  CANCELLED: "Cancelled",
};

function formatTime(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function TransportQueue({ transports, patients, loading, error }: TransportQueueProps) {
  if (error) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 text-tower-error text-xs">
        <AlertTriangle className="h-3.5 w-3.5" />
        <span>Failed to load: {error}</span>
      </div>
    );
  }

  if (loading && transports.length === 0) {
    return (
      <div className="flex items-center justify-center gap-3 py-3 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-2 shrink-0">
          <Truck className="h-4 w-4 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">Loading transports…</p>
      </div>
    );
  }

  if (transports.length === 0) {
    return (
      <div className="flex items-center justify-center gap-3 py-3 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-2 shrink-0">
          <Truck className="h-4 w-4 text-tower-accent/60" />
        </div>
        <div>
          <p className="text-sm text-gray-400">No active transports</p>
          <p className="text-xs text-gray-600">Transport requests will queue here</p>
        </div>
      </div>
    );
  }

  return (
    <div className="divide-y divide-tower-border/50">
      {transports.map((t) => {
        const patient = patients[t.patient_id];
        return (
          <div
            key={t.id}
            className="flex items-center gap-3 px-3 py-2 hover:bg-white/[0.02] transition-colors text-xs"
          >
            {/* Priority badge */}
            <span
              className={cn(
                "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase shrink-0",
                transportPriorityBadge(t.priority)
              )}
            >
              {t.priority}
            </span>

            {/* Route */}
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <span className="text-gray-200 font-medium truncate">
                {patient?.name ?? t.patient_id}
              </span>
              <span className="text-gray-500 shrink-0 flex items-center gap-1">
                <span className="truncate max-w-[60px]" title={t.from_location}>{t.from_location}</span>
                <ArrowRight className="h-3 w-3" />
                <span className="truncate max-w-[60px]" title={t.to_location}>{t.to_location}</span>
              </span>
            </div>

            {/* State */}
            <span className="text-gray-400 shrink-0">
              {stateLabel[t.state] ?? t.state}
            </span>

            {/* Scheduled time */}
            <span className="text-gray-500 font-mono shrink-0">
              {formatTime(t.scheduled_time)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
