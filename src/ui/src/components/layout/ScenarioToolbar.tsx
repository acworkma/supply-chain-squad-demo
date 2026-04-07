import { useEffect, useMemo } from "react";
import { Radio, ScanLine } from "lucide-react";
import { cn } from "@/lib/utils";

type DemoPhase = "upload" | "analysis" | "dashboard";

interface ScenarioToolbarProps {
  eventsConnected: boolean;
  messagesConnected: boolean;
  phase: DemoPhase;
  onNewScan?: () => void;
  closetName?: string;
  uploadedImage?: File | null;
}

export function ScenarioToolbar({ eventsConnected, messagesConnected, phase, onNewScan, closetName, uploadedImage }: ScenarioToolbarProps) {

  const connected = eventsConnected || messagesConnected;

  // Stable thumbnail URL for the uploaded image
  const thumbnailUrl = useMemo(() => {
    if (!uploadedImage) return null;
    return URL.createObjectURL(uploadedImage);
  }, [uploadedImage]);

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (thumbnailUrl) URL.revokeObjectURL(thumbnailUrl); };
  }, [thumbnailUrl]);

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-tower-surface border-b border-tower-border rounded-t-lg">
      {/* ── Phase-Aware Controls ── */}
      <div className="flex items-center gap-2">
        {phase === "dashboard" ? (
          <>
            {/* New Scan button replaces scenario dropdown in dashboard phase */}
            <button
              onClick={onNewScan}
              className={cn(
                "inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
                "border border-tower-accent/30 bg-tower-accent/10 text-tower-accent",
                "hover:bg-tower-accent/20 hover:border-tower-accent/50",
              )}
            >
              <ScanLine className="h-3 w-3" />
              New Scan
            </button>

            {/* Closet thumbnail + name */}
            {thumbnailUrl && closetName && (
              <div className="flex items-center gap-2 ml-1 pl-2 border-l border-tower-border">
                <img
                  src={thumbnailUrl}
                  alt={closetName}
                  className="h-6 w-6 rounded object-cover border border-tower-border"
                />
                <span className="text-xs text-gray-400 font-medium">{closetName}</span>
              </div>
            )}
          </>
        ) : (
          /* Upload / analysis phases — minimal toolbar, just show app title */
          <span className="text-sm font-semibold text-gray-300 tracking-wide">Supply Chain Command Center</span>
        )}
      </div>

      {/* ── Spacer ── */}
      <div className="flex-1" />

      {/* ── Connection Status ── */}
      <div className="flex items-center gap-1.5 text-xs">
        <Radio className="h-3 w-3 text-gray-500" />
        <span
          className={cn(
            "inline-flex items-center gap-1.5 font-medium",
            connected ? "text-tower-success" : "text-tower-error"
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              connected ? "bg-tower-success" : "bg-tower-error"
            )}
          />
          {connected ? "Connected" : "Disconnected"}
        </span>
      </div>
    </div>
  );
}
