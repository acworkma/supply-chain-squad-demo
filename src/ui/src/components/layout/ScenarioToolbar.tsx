import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Play, RotateCcw, Radio, ChevronDown, ScanLine } from "lucide-react";
import { cn } from "@/lib/utils";

type DemoPhase = "upload" | "analysis" | "dashboard";

interface ScenarioToolbarProps {
  eventsConnected: boolean;
  messagesConnected: boolean;
  onReset?: () => void;
  phase: DemoPhase;
  onNewScan?: () => void;
  closetName?: string;
  uploadedImage?: File | null;
}

interface ScenarioStatus {
  name: string;
  running: boolean;
}

interface ScenarioOption {
  label: string;
  endpoint: string;
  hoverColor: string;
}

interface ScenarioGroup {
  category: string;
  items: ScenarioOption[];
}

const SCENARIO_GROUPS: ScenarioGroup[] = [
  {
    category: "ICO",
    items: [
      { label: "Routine Restock", endpoint: "/api/scenario/routine-restock", hoverColor: "hover:text-tower-accent" },
    ],
  },
  {
    category: "OR",
    items: [
      { label: "PO Approval", endpoint: "/api/scenario/critical-shortage", hoverColor: "hover:text-tower-warning" },
    ],
  },
];

export function ScenarioToolbar({ eventsConnected, messagesConnected, onReset, phase, onNewScan, closetName, uploadedImage }: ScenarioToolbarProps) {
  const [scenario, setScenario] = useState<ScenarioStatus | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const triggerScenario = useCallback(async (endpoint: string, name: string) => {
    setMenuOpen(false);
    setTriggering(true);
    setScenario({ name, running: true });
    // Clear stale events/messages so the approval modal can detect new ones
    onReset?.();
    try {
      const res = await fetch(endpoint, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setTimeout(() => setScenario(null), 30_000);
    } catch {
      setScenario({ name, running: false });
      setTimeout(() => setScenario(null), 5_000);
    } finally {
      setTriggering(false);
    }
  }, [onReset]);

  const handleReset = useCallback(async () => {
    setTriggering(true);
    setScenario(null);
    try {
      const res = await fetch("/api/scenario/seed", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onReset?.();
    } catch {
      // silent — state poll will reflect reality
    } finally {
      setTriggering(false);
    }
  }, [onReset]);

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

            {/* Scenario dropdown (secondary) */}
            <div className="relative ml-1" ref={menuRef}>
              <button
                onClick={() => setMenuOpen((v) => !v)}
                disabled={triggering}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
                  "border border-tower-border bg-tower-bg text-gray-300",
                  "hover:border-tower-accent/50 hover:text-tower-accent",
                  "disabled:opacity-40 disabled:cursor-not-allowed"
                )}
              >
                <Play className="h-3 w-3" />
                Run Scenario
                <ChevronDown className={cn("h-3 w-3 transition-transform", menuOpen && "rotate-180")} />
              </button>

              {menuOpen && (
                <div className="absolute left-0 top-full mt-1 z-50 w-52 rounded border border-tower-border bg-tower-surface shadow-lg py-1">
                  {SCENARIO_GROUPS.map((group) => (
                    <div key={group.category}>
                      <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-gray-500 font-semibold">
                        {group.category}
                      </div>
                      {group.items.map((item) => (
                        <button
                          key={item.endpoint}
                          onClick={() => triggerScenario(item.endpoint, item.label)}
                          className={cn(
                            "w-full text-left px-3 py-1.5 text-xs text-gray-300 transition-colors",
                            "hover:bg-white/[0.05]",
                            item.hoverColor
                          )}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={handleReset}
              disabled={triggering}
              className={cn(
                "inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
                "border border-tower-border bg-tower-bg text-gray-300",
                "hover:border-gray-500 hover:text-gray-100",
                "disabled:opacity-40 disabled:cursor-not-allowed"
              )}
            >
              <RotateCcw className="h-3 w-3" />
              Reset
            </button>
          </>
        ) : (
          /* Upload / analysis phases — minimal toolbar, just show app title */
          <span className="text-sm font-semibold text-gray-300 tracking-wide">Supply Chain Command Center</span>
        )}
      </div>

      {/* ── Scenario Status ── */}
      {scenario && (
        <div className="flex items-center gap-2 ml-2 text-xs text-gray-400">
          <span className="text-gray-500">Scenario:</span>
          <span className="text-gray-200 font-medium">{scenario.name}</span>
          <span className="text-gray-500">—</span>
          {scenario.running ? (
            <span className="inline-flex items-center gap-1 text-tower-accent">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-tower-accent opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-tower-accent" />
              </span>
              Running
            </span>
          ) : (
            <span className="text-tower-error">Failed</span>
          )}
        </div>
      )}

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
