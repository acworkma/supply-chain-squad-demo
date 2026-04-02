import { useEffect, useLayoutEffect, useRef, useState, useMemo, useCallback } from "react";
import { cn } from "@/lib/utils";
import { agentColor, intentTagBadge } from "@/lib/colors";
import type { AgentMessage, IntentTag } from "@/types/api";

/* ── Agent definitions ─────────────────────────────────────────── */

interface AgentDef {
  name: string;
  role: string;
}

const ORCHESTRATOR: AgentDef = { name: "bed-coordinator", role: "Bed Coordinator Assistant" };

const SPECIALISTS: AgentDef[] = [
  { name: "predictive-capacity", role: "Predictive Capacity" },
  { name: "policy-safety", role: "Policy & Safety" },
  { name: "bed-allocation", role: "Bed Allocation" },
  { name: "evs-tasking", role: "EVS Tasking" },
  { name: "transport-ops", role: "Transport Ops" },
];

const SIMULATED_ACTORS: AgentDef[] = [
  { name: "er-doctor", role: "ER Physician" },
  { name: "surgical-team", role: "Surgical Team" },
  { name: "unit-supervisor", role: "Unit Supervisor" },
];

/* ── Line descriptor ──────────────────────────────────────────── */

interface Line {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  agentName: string;
}

/* ── Props ─────────────────────────────────────────────────────── */

interface AgentNetworkProps {
  messages: AgentMessage[];
}

/* ── Component ─────────────────────────────────────────────────── */

export function AgentNetwork({ messages }: AgentNetworkProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const orchRef = useRef<HTMLDivElement>(null);
  const specRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [lines, setLines] = useState<Line[]>([]);
  const [flashAgent, setFlashAgent] = useState<string | null>(null);
  const prevCountRef = useRef(0);

  /* ── Derive activity state from messages ── */

  const activeAgent = useMemo(() => {
    if (messages.length === 0) return null;
    return messages[messages.length - 1].agent_name;
  }, [messages]);

  const lastIntentByAgent = useMemo(() => {
    const map: Record<string, IntentTag> = {};
    for (const m of messages) {
      map[m.agent_name] = m.intent_tag;
    }
    return map;
  }, [messages]);

  /* ── Flash on new message ── */

  useEffect(() => {
    if (messages.length > prevCountRef.current && messages.length > 0) {
      const latest = messages[messages.length - 1].agent_name;
      setFlashAgent(latest);
      const timer = setTimeout(() => setFlashAgent(null), 400);
      return () => clearTimeout(timer);
    }
    prevCountRef.current = messages.length;
  }, [messages]);

  /* ── Compute SVG connector lines ── */

  const recomputeLines = useCallback(() => {
    const container = containerRef.current;
    const orch = orchRef.current;
    if (!container || !orch) return;

    const cRect = container.getBoundingClientRect();
    const oRect = orch.getBoundingClientRect();

    const newLines: Line[] = [];
    for (let i = 0; i < SPECIALISTS.length; i++) {
      const el = specRefs.current[i];
      if (!el) continue;
      const sRect = el.getBoundingClientRect();
      newLines.push({
        x1: oRect.left + oRect.width / 2 - cRect.left,
        y1: oRect.top + oRect.height - cRect.top,
        x2: sRect.left + sRect.width / 2 - cRect.left,
        y2: sRect.top - cRect.top,
        agentName: SPECIALISTS[i].name,
      });
    }
    setLines(newLines);
  }, []);

  useLayoutEffect(() => {
    recomputeLines();
  }, [recomputeLines]);

  useEffect(() => {
    const handleResize = () => recomputeLines();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [recomputeLines]);

  /* ── Render ── */

  return (
    <div ref={containerRef} className="relative flex flex-col items-center justify-center gap-5 h-full px-6 py-3">
      {/* SVG connector lines */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden>
        {lines.map((line) => {
          const isActive = activeAgent === line.agentName;
          const colors = agentColor(line.agentName);
          return (
            <line
              key={line.agentName}
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
              stroke={isActive ? "currentColor" : "#374151"}
              strokeWidth={isActive ? 2 : 1}
              strokeDasharray={isActive ? "none" : "4 3"}
              className={cn("transition-all duration-300", isActive && colors.text)}
            />
          );
        })}
      </svg>

      {/* Simulated actors (left side — only show if they've sent messages) */}
      {(() => {
        const activeActors = SIMULATED_ACTORS.filter(a => lastIntentByAgent[a.name]);
        if (activeActors.length === 0) return null;
        return (
          <div className="absolute left-4 top-1/2 -translate-y-1/2 flex flex-col gap-2">
            {activeActors.map((actor) => (
              <div
                key={actor.name}
                className={cn(
                  "flex items-center gap-2 rounded-lg border border-dashed px-2.5 py-1.5 text-[10px]",
                  "bg-tower-surface",
                  activeAgent === actor.name
                    ? "border-green-500/60 text-green-400 shadow-[0_0_8px_-3px_rgba(34,197,94,0.4)]"
                    : "border-green-500/30 text-gray-500"
                )}
              >
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className={cn(
                    "relative inline-flex h-2 w-2 rounded-full transition-colors duration-300",
                    activeAgent === actor.name ? "bg-green-400 animate-pulse" : "bg-gray-600"
                  )} />
                </span>
                <span className={cn("font-semibold truncate", activeAgent === actor.name ? "text-green-400" : "text-gray-400")}>
                  {actor.role}
                </span>
                <span className="text-[8px] text-gray-600 italic">simulated</span>
              </div>
            ))}
          </div>
        );
      })()}

      {/* Orchestrator (top center) */}
      <AgentNode
        ref={orchRef}
        agent={ORCHESTRATOR}
        isActive={activeAgent === ORCHESTRATOR.name}
        isFlashing={flashAgent === ORCHESTRATOR.name}
        lastIntent={lastIntentByAgent[ORCHESTRATOR.name]}
      />

      {/* Specialists (bottom row) */}
      <div className="flex items-start justify-center gap-4 flex-wrap">
        {SPECIALISTS.map((spec, i) => (
          <AgentNode
            key={spec.name}
            ref={(el: HTMLDivElement | null) => { specRefs.current[i] = el; }}
            agent={spec}
            isActive={activeAgent === spec.name}
            isFlashing={flashAgent === spec.name}
            lastIntent={lastIntentByAgent[spec.name]}
          />
        ))}
      </div>
    </div>
  );
}

/* ── AgentNode ─────────────────────────────────────────────────── */

import { forwardRef } from "react";

interface AgentNodeProps {
  agent: AgentDef;
  isActive: boolean;
  isFlashing: boolean;
  lastIntent?: IntentTag;
}

const AgentNode = forwardRef<HTMLDivElement, AgentNodeProps>(
  function AgentNode({ agent, isActive, isFlashing, lastIntent }, ref) {
    const colors = agentColor(agent.name);

    return (
      <div
        ref={ref}
        className={cn(
          "relative flex items-center gap-2.5 rounded-lg border px-3 py-2 text-xs transition-all duration-300 min-w-[140px]",
          "bg-tower-surface",
          isActive
            ? `border-current ${colors.text} shadow-[0_0_12px_-3px_currentColor]`
            : "border-tower-border text-gray-500"
        )}
      >
        {/* Blinking indicator */}
        <span className="relative flex h-2.5 w-2.5 shrink-0">
          {/* Flash ping (on new message) */}
          {isFlashing && (
            <span
              className={cn(
                "absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping",
                colors.bg
              )}
            />
          )}
          {/* Continuous pulse (while active) */}
          <span
            className={cn(
              "relative inline-flex h-2.5 w-2.5 rounded-full transition-colors duration-300",
              isActive ? cn(colors.bg.replace("/20", ""), "animate-pulse") : "bg-gray-600"
            )}
          />
        </span>

        {/* Name + intent */}
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className={cn("font-semibold truncate", isActive ? colors.text : "text-gray-300")}>
            {agent.role}
          </span>
          {lastIntent && (
            <span
              className={cn(
                "inline-flex items-center self-start rounded px-1.5 py-0.5 text-[9px] font-bold uppercase leading-none",
                intentTagBadge(lastIntent)
              )}
            >
              {lastIntent}
            </span>
          )}
        </div>
      </div>
    );
  }
);
