import { useState, useCallback, useRef, useEffect } from "react";
import { Play, RotateCcw, Radio, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface ScenarioToolbarProps {
  eventsConnected: boolean;
  messagesConnected: boolean;
  onReset?: () => void;
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

export function ScenarioToolbar({ eventsConnected, messagesConnected, onReset }: ScenarioToolbarProps) {
  const [scenario, setScenario] = useState<ScenarioStatus | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const connected = eventsConnected || messagesConnected;

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
      {/* ── Scenario Dropdown ── */}
      <div className="flex items-center gap-2">
        <div className="relative" ref={menuRef}>
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
