import { Users, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { patientStateBadge } from "@/lib/colors";
import type { Patient } from "@/types/api";

interface PatientQueueProps {
  patients: Patient[];
  loading: boolean;
  error: string | null;
}

function formatWait(requestedAt: string): string {
  const diff = Date.now() - new Date(requestedAt).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "<1m";
  if (mins < 60) return `${mins}m`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

const acuityColors: Record<number, string> = {
  1: "text-red-400",
  2: "text-orange-400",
  3: "text-yellow-400",
  4: "text-blue-400",
  5: "text-gray-400",
};

export function PatientQueue({ patients, loading, error }: PatientQueueProps) {
  if (error) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 text-tower-error text-xs">
        <AlertTriangle className="h-3.5 w-3.5" />
        <span>Failed to load: {error}</span>
      </div>
    );
  }

  if (loading && patients.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-3 mb-3">
          <Users className="h-5 w-5 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">Loading patients…</p>
      </div>
    );
  }

  if (patients.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-3 mb-3">
          <Users className="h-5 w-5 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">No patients in queue</p>
        <p className="text-xs text-gray-600 mt-1">Start a scenario to see incoming patients</p>
      </div>
    );
  }

  // Sort: highest acuity first (lowest number), then longest wait
  const sorted = [...patients].sort((a, b) => {
    if (a.acuity_level !== b.acuity_level) return a.acuity_level - b.acuity_level;
    return new Date(a.requested_at).getTime() - new Date(b.requested_at).getTime();
  });

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-gray-500 uppercase tracking-wider border-b border-tower-border">
          <th className="text-left px-3 py-2 font-medium">Patient</th>
          <th className="text-left px-3 py-2 font-medium">MRN</th>
          <th className="text-left px-3 py-2 font-medium">State</th>
          <th className="text-left px-3 py-2 font-medium">Source</th>
          <th className="text-left px-3 py-2 font-medium">Location</th>
          <th className="text-center px-3 py-2 font-medium">Acuity</th>
          <th className="text-left px-3 py-2 font-medium">Bed</th>
          <th className="text-right px-3 py-2 font-medium">Wait</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((p) => (
          <tr
            key={p.id}
            className="border-b border-tower-border/50 hover:bg-white/[0.02] transition-colors"
          >
            <td className="px-3 py-1.5 text-gray-200 font-medium truncate max-w-[120px]">
              {p.name}
            </td>
            <td className="px-3 py-1.5 text-gray-400 font-mono">{p.mrn}</td>
            <td className="px-3 py-1.5">
              <span
                className={cn(
                  "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold border transition-colors",
                  patientStateBadge(p.state)
                )}
              >
                {p.state.replace(/_/g, " ")}
              </span>
            </td>
            <td className="px-3 py-1.5 text-gray-400 truncate max-w-[80px]">
              {p.admission_source?.replace(/_/g, " ") ?? "ER"}
            </td>
            <td className="px-3 py-1.5 text-gray-400 truncate max-w-[100px]">
              {p.current_location}
            </td>
            <td className={cn("px-3 py-1.5 text-center font-bold font-mono", acuityColors[p.acuity_level] ?? "text-gray-400")}>
              {p.acuity_level}
            </td>
            <td className="px-3 py-1.5 text-gray-400 font-mono">
              {p.assigned_bed_id ?? "—"}
            </td>
            <td className="px-3 py-1.5 text-right text-gray-400 font-mono">
              {formatWait(p.requested_at)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
