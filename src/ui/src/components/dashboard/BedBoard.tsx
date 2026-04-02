import { BedDouble, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { bedStateBadge, bedStateDotColor } from "@/lib/colors";
import type { Bed, Patient, HospitalConfig } from "@/types/api";

interface BedBoardProps {
  beds: Bed[];
  patients: Record<string, Patient>;
  hospitalConfig: HospitalConfig | null;
  loading: boolean;
  error: string | null;
}

export function BedBoard({ beds, patients, hospitalConfig, loading, error }: BedBoardProps) {
  if (error) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 text-tower-error text-xs">
        <AlertTriangle className="h-3.5 w-3.5" />
        <span>Failed to load: {error}</span>
      </div>
    );
  }

  if (loading && beds.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-3 mb-3">
          <BedDouble className="h-5 w-5 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">Loading beds…</p>
      </div>
    );
  }

  if (beds.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <div className="rounded-full bg-tower-accent/10 p-3 mb-3">
          <BedDouble className="h-5 w-5 text-tower-accent/60" />
        </div>
        <p className="text-sm text-gray-400">No bed data loaded</p>
        <p className="text-xs text-gray-600 mt-1">Bed assignments will appear here during scenarios</p>
      </div>
    );
  }

  // Group beds by unit
  const unitMap = new Map<string, Bed[]>();
  for (const bed of beds) {
    const group = unitMap.get(bed.unit) ?? [];
    group.push(bed);
    unitMap.set(bed.unit, group);
  }

  // Sort units alphabetically, beds by room+letter
  const sortedUnits = [...unitMap.entries()].sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="p-3 space-y-3">
      {sortedUnits.map(([unit, unitBeds]) => {
        const sorted = unitBeds.sort((a, b) =>
          `${a.room_number}${a.bed_letter}`.localeCompare(`${b.room_number}${b.bed_letter}`)
        );
        const unitCfg = hospitalConfig?.units?.[unit] ?? null;
        const campusCfg = unitCfg?.campus_id && hospitalConfig?.campuses?.[unitCfg.campus_id]
          ? hospitalConfig.campuses[unitCfg.campus_id]
          : null;
        return (
          <div key={unit}>
            <h3 className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1.5 px-1">
              {unit}
              {unitCfg && (
                <span className="ml-1.5 normal-case text-gray-600">
                  — {unitCfg.specialty}{campusCfg && campusCfg.id !== "main" ? ` · ${campusCfg.name}` : ""}
                </span>
              )}
            </h3>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(110px,1fr))] gap-1.5">
              {sorted.map((bed) => {
                const patient = bed.patient_id ? patients[bed.patient_id] : null;
                const reservedPatient = bed.reserved_for_patient_id
                  ? patients[bed.reserved_for_patient_id]
                  : null;

                return (
                  <div
                    key={bed.id}
                    className={cn(
                      "rounded border px-2 py-1.5 text-[11px] transition-colors",
                      bedStateBadge(bed.state),
                      bed.reserved_for_patient_id && "ring-1 ring-amber-500/30"
                    )}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", bedStateDotColor(bed.state))} />
                      <span className="font-semibold font-mono">
                        {bed.room_number}{bed.bed_letter}
                      </span>
                      <span className="ml-auto text-[9px] opacity-70 uppercase">
                        {bed.state.replace(/_/g, " ")}
                      </span>
                    </div>
                    {patient && (
                      <p className="text-[10px] opacity-80 truncate" title={patient.name}>
                        {patient.name}
                      </p>
                    )}
                    {reservedPatient && !patient && (
                      <p className="text-[10px] opacity-70 truncate italic" title={`Reserved: ${reservedPatient.name}`}>
                        ↳ {reservedPatient.name}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
